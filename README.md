# GetFnative
A script that help find the native fractional resolution of upscaled material (mostly anime)

## How it works

The general idea can be found in [anibin's blog](https://anibin.blogspot.com/2014/01/blog-post_3155.html).

Suppose the native integer resolution is `base_width x base_height`, upscaled and cropped to only keep the central region (typically 1920 x 1080). This script performs a naive search on the fractional `src_height`.
The search is taken in the interval from `min` to `max` with a given `step_length`.
These parameters can be specified using `-min`, `-max` and `-sl`, respectively.

You must specify `base_height` using `-bh`, and optionally specify `base_width` using `-bw`.
Note that even and odd values of `base_height` or `base_width` behave quite differently because of the cropping method.
With the wrong parity used you might see a spike in the opposite direction.

Pass `-m w` or `-m h` to descale only in width or in height. By default both dimensions are considered.

To acquire the cropping parameters used in descaling, please refer to the function `descale_cropping_args`.

## Examples

```python
python -m getfnative script.vpy -bh 864 -f 1001
```
This examines frame 1001 from the output index 0 of the provided script, by checking the `src_height` values of 764.0, 764.25, 764.5, ..., 864.0.

```python
python -m getfnative script.vpy -bh 864 -f 1001 -min 820 -max 840 -sl 0.1
```
The values of `src_height` to be checked becomes 820, 820.1, 820.2, ..., 840.

```python
from getfnative import descale_cropping_args
d_args = descale_cropping_args(clip, src_height=830.77, base_height=864)
descaled = core.descale.Debilinear(clip, **d_args)
f1 = 1
f2 = 1
upscaled = descaled.nnedi3.nnedi3(field=f1, dh=True).std.Transpose().nnedi3.nnedi3(field=f2, dh=True).std.Transpose()
c_args = dict(
    width = 1920,
    height = 1080,
    src_width = d_args['src_width'] * 2,
    src_height = d_args['src_height'] * 2,
    src_left = d_args['src_left'] * 2 + 0.5 - f2,
    src_top = d_args['src_top'] * 2 + 0.5 - f1
)
final = core.resize.Bicubic(upscaled, **c_args)
```
A demo script for anti-aliasing, assuming you have got an estimated `src_height`, say, 830.77, you will descale, upscale with nnedi3, and resize to 1920x1080.

## Acknowledgment

Thanks to the authors of [getnative](https://github.com/Infiziert90/getnative) and [Yuuno](https://github.com/Irrational-Encoding-Wizardry/yuuno).

**I don't know what I'm doing.**
