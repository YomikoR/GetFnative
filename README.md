# GetFnative
A script that help find the native fractional resolution of upscaled material (mostly anime)

## How it works

The general idea can be found in [anibin's blog](https://anibin.blogspot.com/2014/01/blog-post_3155.html).

Suppose the native integer resolution is `base_width x base_height`, upscaled and cropped to only keep the central region (typically 1920 x 1080). This script performs a naive search on the fractional `src_height`.
The search is performed in the interval from `min` to `max` with a given `step_length`.
These parameters can be specified using `-min`, `-max` and `-sl`, respectively.

You must specify `base_height` using `-bh`, and optionally specify `base_width` using `-bw`.
Note that even and odd values of `base_height` or `base_width` behave quite differently because of the cropping method.
With the wrong parity used you might see a spike in the opposite direction.

To acquire the cropping parameters used in descaling, please refer to the function `descale_cropping_args`.

There is a minor memory leak caused by calling `get_frame_async` but you may simply ignore it.

## Acknowledgment

Thanks to the authors of [getnative](https://github.com/Infiziert90/getnative) and [Yuuno](https://github.com/Irrational-Encoding-Wizardry/yuuno).

**I don't know what I'm doing.**
