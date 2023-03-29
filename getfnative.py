from __future__ import annotations

import argparse
import gc
import os
import runpy
import time
from functools import partial
from math import floor
from typing import Callable, Optional, Union

import matplotlib.pyplot as plt
import vapoursynth as vs
from matplotlib.figure import figaspect

core = vs.core

__all__ = ['descale_cropping_args']


def get_scaler(kernel: str,
               b: int = 0,
               c: float = 1 / 2,
               taps: int = 3
               ) -> Callable[..., vs.VideoNode]:
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
        raise ValueError('get_scaler: invalid kernel specified.')


def vpy_source_filter(path: str) -> vs.VideoNode:
    runpy.run_path(path, {}, '__vapoursynth__')
    output = vs.get_output(0)
    if not isinstance(output, vs.VideoNode):
        output = output[0]
    return output


def to_float(str_value: str) -> float:
    if set(str_value) - set("0123456789./-"):
        raise argparse.ArgumentTypeError(
            "Invalid characters in float parameter")
    try:
        return eval(str_value) if "/" in str_value else float(str_value)
    except (SyntaxError, ZeroDivisionError, TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "Exception while parsing float") from None


def descale_cropping_args(clip: vs.VideoNode, # letterbox-free source clip
                          src_height: float,
                          base_height: int,
                          base_width: int,
                          crop_top: int = 0,
                          crop_bottom: int = 0,
                          crop_left: int = 0,
                          crop_right: int = 0,
                          mode: str = 'wh'
                          ) -> dict[str, Union[int, float]]:
    ratio = src_height / (clip.height + crop_top + crop_bottom)
    src_width = ratio * (clip.width + crop_left + crop_right)

    cropped_src_width = ratio * clip.width
    margin_left = (base_width - src_width) / 2 + ratio * crop_left
    margin_right = (base_width - src_width) / 2 + ratio * crop_right
    cropped_width = base_width - floor(margin_left) - floor(margin_right)
    cropped_src_left = margin_left - floor(margin_left)

    cropped_src_height = ratio * clip.height
    margin_top = (base_height - src_height) / 2 + ratio * crop_top
    margin_bottom = (base_height - src_height) / 2 + ratio * crop_bottom
    cropped_height = base_height - floor(margin_top) - floor(margin_bottom)
    cropped_src_top = margin_top - floor(margin_top)

    args = dict(
        width=clip.width + crop_left + crop_right,
        height=clip.height + crop_top + crop_bottom
    )
    args_w = dict(
        width=cropped_width,
        src_width=cropped_src_width,
        src_left=cropped_src_left
    )
    args_h = dict(
        height=cropped_height,
        src_height=cropped_src_height,
        src_top=cropped_src_top
    )
    if 'w' in mode.lower():
        args.update(args_w)
    if 'h' in mode.lower():
        args.update(args_h)
    return args


def gen_descale_error(clip: vs.VideoNode,
                      crop_top: int,
                      crop_bottom: int,
                      crop_left: int,
                      crop_right: int,
                      frame_no: int,
                      base_height: int,
                      base_width: int,
                      src_heights: list[float],
                      kernel: str = 'bicubic',
                      b: int = 0,
                      c: float = 1 / 2,
                      taps: int = 3,
                      mode: str = 'wh',
                      thr: float = 0.015,
                      show_plot: bool = True,
                      save_path: Optional[os.PathLike] = None
                      ) -> None:
    num_samples = len(src_heights)
    clips = clip[frame_no].resize.Point(
        format=vs.GRAYS, matrix_s='709' if clip.format.color_family == vs.RGB else None) * num_samples
    # Descale
    scaler = get_scaler(kernel, b, c, taps)

    def _rescale(n: int, clip: vs.VideoNode) -> vs.VideoNode:
        cropping_args = descale_cropping_args(
            clip, src_heights[n], base_height, base_width, crop_top, crop_bottom, crop_left, crop_right, mode)
        descaled = core.descale.Descale(clip, kernel=kernel, b=b, c=c, taps=taps, **cropping_args)
        cropping_args.update(width=clip.width, height=clip.height)
        return scaler(descaled, **cropping_args)
    rescaled = core.std.FrameEval(clips, partial(_rescale, clip=clips))
    diff = core.std.Expr([clips, rescaled], f'x y - abs dup {thr} > swap 0 ?')
    diff = diff.std.Crop(10, 10, 10, 10).std.PlaneStats()
    # Collect error
    errors = [0.0] * num_samples
    starttime = time.time()
    for n, f in enumerate(diff.frames()):
        print(f'\r{n + 1}/{num_samples}', end='')
        errors[n] = f.props['PlaneStatsAverage']
    print(f'\nDone in {time.time() - starttime:.2f}s')
    gc.collect()
    # Plot
    p = plt.figure()
    plt.close('all')
    plt.style.use('dark_background')
    _, ax = plt.subplots(figsize=figaspect(1/2))
    ax.plot(src_heights, errors, '.w-', linewidth=1)
    ax.set(xlabel='src_height', ylabel='Error', yscale='log')
    if save_path is not None:
        plt.savefig(save_path)
    if show_plot:
        plt.show()
    plt.close(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Find the native fractional resolution of upscaled material (mostly anime)')
    parser.add_argument('--frame', '-f', dest='frame_no', type=int,
                        default=0, help='Specify a frame for the analysis, default is 0')
    parser.add_argument('--kernel', '-k', dest='kernel', type=str.lower,
                        default='bicubic', help='Resize kernel to be used')
    parser.add_argument('--bicubic-b', '-b', dest='b', type=to_float,
                        default='0', help='B parameter of bicubic resize')
    parser.add_argument('--bicubic-c', '-c', dest='c', type=to_float,
                        default='1/2', help='C parameter of bicubic resize')
    parser.add_argument('--lanczos-taps', '-t', dest='taps',
                        type=int, default=3, help='Taps parameter of lanczos resize')
    parser.add_argument('--base-height', '-bh', dest='bh', type=int,
                        default=None, help='Base integer height before cropping')
    parser.add_argument('--base-width', '-bw', dest='bw', type=int,
                        default=None, help='Base integer width before cropping')
    parser.add_argument('--crop-top', '-ct', dest='ct', type=int,
                        default='0', help='Top border size of letterboxing')
    parser.add_argument('--crop-bottom', '-cb', dest='cb', type=int,
                        default='0', help='Bottom border size of letterboxing')
    parser.add_argument('--crop-left', '-cl', dest='cl', type=int,
                        default='0', help='Left border size of letterboxing')
    parser.add_argument('--crop-right', '-cr', dest='cr', type=int,
                        default='0', help='Right border size of letterboxing')
    parser.add_argument('--min-src-height', '-min', dest='sh_min', type=to_float,
                        default=None, help='Minimum native src_height to consider')
    parser.add_argument('--max-src-height', '-max', dest='sh_max', type=to_float,
                        default=None, help='Maximum native src_height to consider')
    parser.add_argument('--step-length', '-sl', dest='sh_step', type=to_float,
                        default='0.25', help='Step length of src_height searching')
    parser.add_argument('--threshold', '-thr', dest='thr', type=to_float,
                        default='0.015', help='Threshold for calculating descaling error')
    parser.add_argument('--mode', '-m', dest='mode', type=str.lower, default='wh',
                        help='Mode for descaling, options are wh (default), w (descale in width only) and h (descale in height only)')
    parser.add_argument('--save-dir', '-dir', dest='save_dir', type=str,
                        default=None, help='Location of output error plot directory')
    parser.add_argument('--save-ext', '-ext', dest='save_ext', type=str,
                        default='svg', help='File extension of output error plot file')
    parser.add_argument(dest='input_file', type=str,
                        help='Absolute or relative path to the input VPY script')
    args = parser.parse_args()

    ext = os.path.splitext(args.input_file)[1]
    if ext.lower() in {'.py', '.pyw', '.vpy'}:
        clip = vpy_source_filter(args.input_file)
    elif ext.lower() in {'.png', '.bmp', '.tif', '.tiff', '.webp'}:
        clip = core.imwri.Read(args.input_file, float_output=True)
    else:
        raise ValueError('You should provide either a script or an image.')

    assert args.ct >= 0
    assert args.cb >= 0
    assert args.cl >= 0
    assert args.cr >= 0

    full_height = clip.height + args.ct + args.cb
    full_width = clip.width + args.cl + args.cr

    if args.bh is None:
        base_height = full_height
    else:
        base_height = args.bh
    if args.bw is None:
        base_width = full_width
    else:
        base_width = args.bw
    base_height = full_height - (base_height - full_height) % 2
    base_width = full_width - (base_width - full_width) % 2
    print(f'Using base dimensions with the same parities as {base_width}x{base_height}.')

    if args.save_dir is None:
        dir_out = os.path.join(os.path.dirname(
            args.input_file), 'getfnative_results')
        os.makedirs(dir_out, exist_ok=True)
    else:
        dir_out = args.save_dir
    save_path = dir_out + os.path.sep + \
        f'getfnative-f{args.frame_no}-bh{args.bh}'
    n = 1
    while True:
        if os.path.exists(save_path + f'-{n}.' + args.save_ext):
            n = n + 1
            continue
        else:
            save_path = save_path + f'-{n}.' + args.save_ext
            break

    if args.sh_max is None:
        sh_max = base_height
    else:
        sh_max = args.sh_max
    if args.sh_min is None:
        sh_min = sh_max - 100
    else:
        sh_min = args.sh_min
    assert args.sh_step > 0.0
    assert sh_max <= base_height
    assert sh_min < sh_max - args.sh_step
    max_samples = floor((sh_max - sh_min) / args.sh_step) + 1
    src_heights = [sh_min + n * args.sh_step for n in range(max_samples)]

    gen_descale_error(clip, args.ct, args.cb, args.cl, args.cr, args.frame_no,
                      base_height, base_width, src_heights,
                      args.kernel, args.b, args.c, args.taps, args.mode, args.thr, True, save_path)


if __name__ == '__main__':
    main()
