#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Provider contracts. Concrete adapters can be added without changing the Brain/UI."""
class ProviderError(RuntimeError): pass
class BaseProvider:
    kind="base"
    def generate(self, prompt, **kwargs): raise ProviderError("هذا المزود غير مهيأ.")
class TextProvider(BaseProvider): kind="text"
class ImageProvider(BaseProvider): kind="image"
class VideoProvider(BaseProvider): kind="video"
class MusicProvider(BaseProvider): kind="music"
