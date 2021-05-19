# GetFnative
A script that help find the native fractional resolution of upscaled material (mostly anime)

## How it works

The general idea can be found in [anibin's blog](https://anibin.blogspot.com/2014/01/blog-post_3155.html).

Suppose the native integer resolution is `base_width x base_height`, upscaled and cropped to only keep the central region (typically 1920 x 1080). This script performs a naive search on the fractional `src_height`.

The search is performed in the interval from `min` to `base_height` with a given `step_length`.
These parameters can be specified using `-min`, `-bh` and `-sl`, respectively.

Note that even and odd values of `base_height` or `base_width` (optionally specified using `-bw`) behave quite differently because of the cropping method.
With the wrong parity used you might see a spike in the opposite direction.

There is a minor memory leak caused by calling `get_frame_async` but you may simply ignore it.

## Acknowledgment

Thanks to the authors of [getnative](https://github.com/Infiziert90/getnative) and [Yuuno](https://github.com/Irrational-Encoding-Wizardry/yuuno).

**I don't know what I'm doing.**
