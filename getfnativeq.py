'''
Lite version with some fixed params
'''

from __future__ import annotations

import argparse
import os
import runpy
import time
from functools import partial
from math import floor
from typing import Optional, Union

import matplotlib.pyplot as plt
from matplotlib.figure import figaspect
import vapoursynth as vs
core = vs.core


def vpy_source_filter(path: os.PathLike) -> vs.VideoNode:
    runpy.run_path(path, {}, '__vapoursynth__')
    output = vs.get_output(0)[0]
    assert isinstance(output, vs.VideoNode)
    return output


def descale_cropping_args(clip: vs.VideoNode,
                          src_height: float,
                          base_height: int,
                          base_width: int,
                          mode: str = 'wh'
                          ) -> dict[str, Union[int, float]]:
    src_width = src_height * clip.width / clip.height
    if base_height < src_height:
        base_height += (src_height - base_height) // 2 * 2 + 2
    if base_width < src_width:
        base_width += (src_width - base_width) // 2 * 2 + 2
    cropped_width = base_width - 2 * floor((base_width - src_width) / 2)
    cropped_height = base_height - 2 * floor((base_height - src_height) / 2)
    args = dict(
        width=clip.width,
        height=clip.height
    )
    args_w = dict(
        width=cropped_width,
        src_width=src_width,
        src_left=(cropped_width - src_width) / 2
    )
    args_h = dict(
        height=cropped_height,
        src_height=src_height,
        src_top=(cropped_height - src_height) / 2
    )
    if 'w' in mode.lower():
        args.update(args_w)
    if 'h' in mode.lower():
        args.update(args_h)
    return args


def gen_descale_error(clip: vs.VideoNode,
                      frame_no: int,
                      base_height: int,
                      base_width: int,
                      src_heights: list[float],
                      mode: str = 'wh',
                      save_path: Optional[os.PathLike] = None) -> None:
    num_samples = len(src_heights)
    clips = clip[frame_no].resize.Point(
        format=vs.GRAYS, matrix_s='709' if clip.format.color_family == vs.RGB else None) * num_samples

    def _rescale(n: int, clip: vs.VideoNode) -> vs.VideoNode:
        cropping_args = descale_cropping_args(
            clip, src_heights[n], base_height, base_width, mode)
        descaled = core.descale.Debicubic(clip, b=0, c=1/2, **cropping_args)
        cropping_args.update(width=clip.width, height=clip.height)
        return core.resize.Bicubic(descaled, **cropping_args)
    rescaled = core.std.FrameEval(clips, partial(_rescale, clip=clips))
    diff = core.std.Expr([clips, rescaled], f'x y - abs dup 0.015 > swap 0 ?')
    diff = diff.std.Crop(10, 10, 10, 10).std.PlaneStats()

    errors = [0.0] * num_samples
    starttime = time.time()
    for n, f in enumerate(diff.frames(close=True)):
        print(f'\r{n+1}/{num_samples}', end='')
        errors[n] = f.props['PlaneStatsAverage']
    print(f'\nDone in {time.time() - starttime:2f}s')

    p = plt.figure()
    plt.close('all')
    plt.style.use('dark_background')
    _, ax = plt.subplots(figsize=figaspect(1/2))
    ax.plot(src_heights, errors, '.w-', linewidth=1)
    ax.set(xlabel='Guessed heights', ylabel='Error', yscale='log')
    if save_path is not None:
        plt.savefig(save_path)
    plt.show()
    plt.close(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Find the native fractional resolution of upscaled material (mostly anime)')
    parser.add_argument('--frame', '-f', dest='frame_no', type=int,
                        default=0, help='Specify a frame for the analysis, default is 0')
    parser.add_argument('--base-height', '-bh', dest='bh', type=int,
                        default=None, help='Base integer height before cropping')
    parser.add_argument('--base-width', '-bw', dest='bw', type=int,
                        default=None, help='Base integer width before cropping')
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
    if not ext.lower() in {'.py', '.pyw', '.vpy'}:
        raise ValueError(
            'Input must be a vpy script whose output index 0 is accepted.')
    clip = vpy_source_filter(args.input_file)

    if args.bh is None:
        base_height = clip.height
    else:
        base_height = args.bh
    if args.bw is None:
        base_width = clip.width
    else:
        base_width = args.bw
    base_height = clip.height - (base_height - clip.height) % 2
    base_width = clip.width - (base_width - clip.width) % 2
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

    src_heights = []
    for n in range(7, 50):
        src_heights.append(clip.height / (1.01 + 0.01 * n))
    for n in range(7, 30):
        src_heights.append(clip.height * (0.99 - 0.01 * n))
    src_heights.sort()

    gen_descale_error(clip, args.frame_no, base_height,
                      base_width, src_heights, args.mode, save_path)


if __name__ == '__main__':
    main()
