"""Check local prerequisites; harness capabilities must be checked by the agent."""
import importlib
import json
from pathlib import Path
import platform
import sys
import tempfile


def report():
    root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(root/'scripts'))
    checks = {'platform': platform.system(), 'python': platform.python_version(),
              'python_supported': sys.version_info >= (3, 10),
              'platform_supported': platform.system() in ('Windows', 'Darwin', 'Linux'),
              'virtualenv': sys.prefix != sys.base_prefix}
    errors = []
    packages = {}
    warnings = []
    weather_ready = True
    for name in ('psutil', 'portalocker', 'numpy', 'PIL', 'matplotlib'):
        try:
            module = importlib.import_module(name)
            packages[name] = getattr(module, '__version__', 'available')
        except Exception as exc:
            packages[name] = str(exc)
            if name in ('numpy', 'PIL', 'matplotlib'):
                weather_ready = False
                warnings.append(name + '不可用：天气图可能生成失败；CSV采集仍可启动')
            if name in ('psutil', 'portalocker'):
                errors.append(name + ': ' + str(exc))
    try:
        import portalocker
        import psutil
        psutil.Process().cmdline()
        with tempfile.TemporaryDirectory(dir=root) as temp:
            with (Path(temp)/'probe.lock').open('a') as handle:
                portalocker.lock(handle, portalocker.LOCK_EX)
                portalocker.unlock(handle)
        checks['filesystem_lock_and_process_access'] = True
    except Exception as exc:
        checks['filesystem_lock_and_process_access'] = False
        errors.append(str(exc))
    try:
        from radar_fonts import cjk_font
        font = cjk_font()
    except Exception:
        font = None
    if not font:warnings.append('未发现中文字体，雷达文字可能缺字；请安装Noto Sans CJK SC')
    if not checks['virtualenv']:warnings.append('未使用虚拟环境，请通过uv run python运行')
    return {'ready': checks['python_supported'] and checks['platform_supported'] and not errors,
            'checks': checks, 'packages': packages, 'errors': errors,
            'cjk_font': font, 'weather_ready': weather_ready, 'warnings': warnings,
            'harness': {'shell': '当前命令成功即证明可以执行Python',
                        'image_view': 'unknown: agent须实际打开雷达PNG验证',
                        'interruptible_wait': 'unknown: agent须检查宿主可用工具',
                        'continuous_ai': 'unknown: 后台采集不等于模型自动持续分析'}}


if __name__ == '__main__':
    result = report()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ready'] else 1)
