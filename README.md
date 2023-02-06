# GetFnative
A script that help find the native fractional resolution of upscaled material (mostly anime)

## How it works

The general idea can be found in [anibin's blog](https://anibin.blogspot.com/2014/01/blog-post_3155.html).

### getfnative

Suppose the native integer resolution is `base_width x base_height`, upscaled and cropped to only keep the central region (typically 1920 x 1080).
This script performs a naive search on the fractional `src_height`.
The search is taken in the interval from `min` to `max` with a given `step_length`.
These parameters can be specified using `-min`, `-max` and `-sl`, respectively.

You would like to specify the **parity** of `base_height` (with `-bh`) and `base_width` (with `-bw`).
Default values are identical to the dimensions of the tested clip.
Note that even and odd values of `base_height` or `base_width` behave quite differently because of the cropping method.
With the wrong parity used you might see a spike in the opposite direction.

Pass `-m w` or `-m h` to descale only in width or in height.
This may be helpful for identifying the parity of base dimensions individually.
By default both dimensions are considered.

To acquire the cropping parameters used in descaling, please refer to the function `descale_cropping_args`.

### getfnativeq

Q for quick, as it only checks certain preset values with limited options, such as frame number (`-f`), `base_height` (`-bh`), `base_width` (`-bw`) and mode (`-m`).
Each of the guessed values is corresponding to an upscaling ratio of `1.xx` or a downscaling ratio of `0.xx`, with exactly two decimal numbers.

## Examples

```python
python -m getfnative script.vpy -bh 864 -f 1001
```
This examines frame 1001 from the output index 0 of the provided script, by checking the `src_height` values of 764.0, 764.25, 764.5, ..., 864.0. By default `min = base_height - 100` and `sl = 0.25`.

```python
python -m getfnative script.vpy -bh 864 -f 1001 -min 820 -max 840 -sl 0.1
```
The values of `src_height` to be checked become 820, 820.1, 820.2, ..., 840.

```python
from getfnative import descale_cropping_args
d_args = descale_cropping_args(clip, src_height=830.77, base_height=900, base_width=1600)
descaled = core.descale.Debilinear(clip, **d_args)
f1 = 1
f2 = 1
upscaled = descaled.nnedi3.nnedi3(field=f1, dh=True).std.Transpose().nnedi3.nnedi3(field=f2, dh=True).std.Transpose()
c_args = dict(
    src_width = d_args['src_width'] * 2,
    src_height = d_args['src_height'] * 2,
    src_left = d_args['src_left'] * 2 + 0.5 - f2,
    src_top = d_args['src_top'] * 2 + 0.5 - f1
)
final = core.resize.Bicubic(upscaled, 1920, 1080, **c_args)
```
A demo script for anti-aliasing, assuming you have got an estimated `src_height`, say, 830.77, you will descale, upscale with nnedi3, and resize to 1920x1080. These cropping arguments are the ones used for testing the kernel, and is often suitable for post-processing provided the resizer does not have rather large taps.

## Acknowledgment

Thanks to the authors of [getnative](https://github.com/Infiziert90/getnative) and [Yuuno](https://github.com/Irrational-Encoding-Wizardry/yuuno).

**I don't know what I'm doing.**
