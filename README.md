# GetFnative
A script that help find the native fractional resolution of upscaled material (mostly anime)

## How it works

The general idea can be found in [anibin's blog](https://anibin.blogspot.com/2014/01/blog-post_3155.html).

Suppose the native integer resolution is `(bw, bh)`, upscaled with a ratio `r` while cropped to only keep the central region `(W, H) = (1920, 1080)`. This script performs a naive search on `bH = bh * r`.

The only parameter that must be provided is `bh`. You may pick a multiple of 18 which is slightly larger than the native fractional resolution you guess.

The example below, reported as 806p by getnative, suggests `r=1.34`:
```python
python getfnative.py source.vpy -bh 864
```
![getfnative-f0-bh864-1](https://user-images.githubusercontent.com/64504948/116792318-7aa5f180-aa85-11eb-83a4-19782e920054.png)

There is a minor memory leak which you may simply ignore.

## Acknowledgment

Thanks to the authors of [getnative](https://github.com/Infiziert90/getnative) and [Yuuno](https://github.com/Irrational-Encoding-Wizardry/yuuno).

**I don't know what I'm doing.**
