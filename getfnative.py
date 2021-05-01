import os, sys, gc, time, runpy
import argparse
from threading import RLock
from functools import partial
from math import floor

import vapoursynth as vs
core = vs.core
core.add_cache = False

import matplotlib as mpl
#mpl.use('Agg')
import matplotlib.pyplot as plt


def get_descaler(kernel, b=0, c=1/2, taps=3):
    if kernel == 'bilinear':
        return core.descale.Debilinear
    elif kernel == 'bicubic':
        return partial(core.descale.Debicubic, b=b, c=c)
    elif kernel == 'lanczos':
        return partial(core.descale.Delanczos, taps=taps)
    elif kernel == 'spline16':
        return core.descale.Despline16
    elif kernel == 'spline36':
        return core.descale.Despline36
    elif kernel == 'spline64':
        return core.descale.Despline64
    else:
        raise ValueError('_get_descaler: invalid kernel specified.')


def get_scaler(kernel, b=0, c=1/2, taps=3):
    if kernel == 'bilinear':
        return core.resize.Bilinear
    elif kernel == 'bicubic':
        return partial(core.resize.Bicubic, filter_param_a=b, filter_param_b=c)
    elif kernel == 'lanczos':
        return partial(core.resize.Lanczos, filter_param_a=taps)
    elif kernel == 'spline16':
        return core.resize.Spline16
    elif kernel == 'spline36':
        return core.resize.Spline36
    elif kernel == 'spline64':
        return core.resize.Spline64
    else:
        raise ValueError('_get_scaler: invalid kernel specified.')


# https://github.com/Infiziert90/getnative/blob/c4bfbb07165db315e3c5d89e68f294892b2effaf/getnative/utils.py#L27
def vpy_source_filter(path):
    runpy.run_path(path, {}, '__vapoursynth__')
    return vs.get_output(0)


# https://github.com/stuxcrystal/vapoursynth/blob/9ce5fe890dfc6f60ccedd096f1c5ecef64fe52fb/src/cython/vapoursynth.pyx#L1548
# basically, self -> clip
def frames(clip, prefetch=None, backlog=None):
    if prefetch is None or prefetch <= 0:
        prefetch = vs.core.num_threads
    if backlog is None or backlog < 0:
        backlog = prefetch * 3
    elif backlog < prefetch:
        backlog = prefetch
    
    enum_fut = enumerate(clip.get_frame_async(frameno) for frameno in range(len(clip)))

    finished = False
    running = 0
    lock = RLock()
    reorder = {}

    def _request_next():
        nonlocal finished, running
        with lock:
            if finished:
                return

            ni = next(enum_fut, None)
            if ni is None:
                finished = True
                return

            running += 1

            idx, fut = ni
            reorder[idx] = fut
            fut.add_done_callback(_finished)

    def _finished(f):
        nonlocal finished, running
        with lock:
            running -= 1
            if finished:
                return

            if f.exception() is not None:
                finished = True
                return

            _refill()

    def _refill():
        if finished:
            return
        
        with lock:
            # Two rules: 1. Don't exceed the concurrency barrier
            #            2. Don't exceed unused-frames-backlog
            while (not finished) and (running < prefetch) and len(reorder) < backlog:
                _request_next()

    _refill()

    sidx = 0
    try:
        while (not finished) or (len(reorder) > 0) or running > 0:
            if sidx not in reorder:
                # Spin. Reorder being empty should never happen.
                continue
        
            # Get next requested frame
            fut = reorder[sidx]

            result = fut.result()
            del reorder[sidx]
            _refill()

            sidx += 1
            yield result
    
    finally:
        finished = True
        gc.collect()


# https://github.com/Infiziert90/getnative/blob/c4bfbb07165db315e3c5d89e68f294892b2effaf/getnative/utils.py#L64
def to_float(str_value):
    if set(str_value) - set("0123456789./"):
        raise argparse.ArgumentTypeError("Invalid characters in float parameter")
    try:
        return eval(str_value) if "/" in str_value else float(str_value)
    except (SyntaxError, ZeroDivisionError, TypeError, ValueError):
        raise argparse.ArgumentTypeError("Exception while parsing float") from None


def getw(clip, h, only_even=True):
    w = h * clip.width / clip.height
    w = int(round(w))
    if only_even:
        w = w // 2 * 2
    return w


def gen_cropping_args(clip, bh, bH, mode='wh'):
    W = clip.width
    H = clip.height
    assert bH >= H
    h = bh * H / bH
    w = bh * W / H
    bw = getw(clip, bh)
    ch = bh - 2 * floor((bh - h) / 2)
    cw = bw - 2 * floor((bw - w) / 2)
    args = dict()
    args_w = dict(
        width = cw,
        src_width = w,
        src_left = (cw - w) / 2
    )
    args_h = dict(
        height = ch,
        src_height = h,
        src_top = (ch - h) / 2
    )
    if 'w' in mode.lower():
        args.update(args_w)
    if 'h' in mode.lower():
        args.update(args_h)
    return args


def gen_descale_error(clip, frame_num, bh, bH_min=1080, bH_step=1e-2, bH_num=1000, kernel='bicubic', b=0, c=1/2, taps=3, thr=0.015, mode='wh', save_path=None):
    clip = clip[frame_num]
    clip = clip.resize.Point(format=vs.GRAYS, matrix_s='709' if clip.format.color_family == vs.RGB else None).std.Cache()
    # Descale
    descaler = get_descaler(kernel, b, c, taps)
    scaler = get_scaler(kernel, b, c, taps)
    def _vupscale(n, clip):
        crop_args = gen_cropping_args(clip, bh, bH_min + n * bH_step)
        down = descaler(clip, **crop_args)
        crop_args.update(width=clip.width, height=clip.height)
        return scaler(down, **crop_args)
    clips = clip * bH_num
    rescaled = core.std.FrameEval(clips, partial(_vupscale, clip=clips))
    full_clip = core.std.Expr([clips, rescaled], f'x y - abs dup {thr} > swap 0 ?').std.Crop(10, 10, 10, 10).std.PlaneStats().std.Cache()

    errors = [0.0] * bH_num
    for n, f in enumerate(frames(full_clip)):
        print(f'\r{n}/{bH_num}', end='')
        errors[n] = f.props['PlaneStatsAverage']
    print('\n')

    # plot
    x_bH = [bH_min + n * bH_step for n in range(bH_num)]
    y_err = errors

    p = plt.figure()
    plt.close('all')
    plt.style.use('dark_background')
    plt.plot(x_bH, y_err, '.w-', linewidth=1)
    plt.xlabel('bH')
    plt.ylabel('Error')
    plt.yscale('log')
    if save_path:
        plt.savefig(save_path)
    plt.show()
    plt.close(p)


parser = argparse.ArgumentParser(description='Find the native fractional resolution of upscaled material (mostly anime)')
parser.add_argument('--frame', '-f', dest='frame_num', type=int, default=0, help='Specify a frame for the analysis, default is 0')
parser.add_argument('--kernel', '-k', dest='kernel', type=str.lower, default='bicubic', help='Resize kernel to be used')
parser.add_argument('--bicubic-b', '-b', dest='b', type=to_float, default='0', help='B parameter of bicubic resize')
parser.add_argument('--bicubic-c', '-c', dest='c', type=to_float, default='1/2', help='C parameter of bicubic resize')
parser.add_argument('--lanczos-taps', '-t', dest='taps', type=int, default=3, help='Taps parameter of lanczos resize')
parser.add_argument('--bh', '-bh', dest='bh', type=int, default=None, help='Integer native height before cropping')
parser.add_argument('--min-height', '-min', dest='bH_min', type=to_float, default='1080', help='Minimum height of bH to consider')
parser.add_argument('--step-length', '-sl', dest='bH_step', type=to_float, default='1.0', help='Step length of bH searching')
parser.add_argument('--step-num', '-sn', dest='bH_num', type=int, default=240, help='Step numbers of bH searching')
parser.add_argument('--threshold', '-thr', dest='thr', type=to_float, default='0.015', help='Threshold for descaling error')
parser.add_argument('--mode', '-m', dest='mode', type=str.lower, default='wh', help='Mode for descaling, options are wh (default), w (descale in width only) and h (descale in height only)')
parser.add_argument('--save-path', '-save', dest='save_path', type=str, default=None, help='Output error plot location')


def main():
    parser.add_argument(dest='input_file', type=str, help='Absolute or relative path to the input VPY script')
    args = parser.parse_args()
    ext = os.path.splitext(args.input_file)[1]
    assert ext.lower() in {'.py', '.pyw', '.vpy'}
    clip = vpy_source_filter(args.input_file)

    if args.save_path is None:
        dir_out = os.path.join(os.path.dirname(args.input_file), 'getfnative_results')
        os.makedirs(dir_out, exist_ok=True)
        save_path = dir_out + os.path.sep + f'getfnative-f{args.frame_num}-bh{args.bh}'
        n = 1
        while True:
            if os.path.exists(save_path + f'-{n}.svg'):
                n = n + 1
                continue
            else:
                save_path = save_path + f'-{n}.svg'
                break
    else:
        save_path = args.save_path

    starttime = time.time()

    gen_descale_error(clip, args.frame_num, args.bh, args.bH_min, args.bH_step, args.bH_num, args.kernel, args.b, args.c, args.taps, args.thr, args.mode, save_path)

    print(f'Done in {time.time() - starttime:.2f}s')


if __name__ == '__main__':
    main()

