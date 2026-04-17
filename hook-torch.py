from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('torch')

# Убираем C++ заголовки (не нужны в runtime, ~64 МБ)
datas = [(s, d) for s, d in datas
         if not any(x in s.replace('\\', '/') for x in
                    ['/include/', '\\include\\', 'torch/include'])]
