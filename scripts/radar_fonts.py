"""Discover installed CJK fonts without machine-specific filesystem paths."""
def cjk_font():
    try:
        from matplotlib import font_manager
        fonts=font_manager.fontManager.ttflist
        for family in ('Noto Sans CJK SC','Source Han Sans SC','Microsoft YaHei','PingFang SC','Songti SC','SimHei','WenQuanYi Zen Hei'):
            for font in fonts:
                if font.name==family:return font.fname
    except ImportError:
        pass
    return None

def pillow_font(size):
    from PIL import ImageFont
    path=cjk_font()
    return ImageFont.truetype(path,size) if path else ImageFont.load_default()
