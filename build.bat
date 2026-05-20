@echo off
REM 合同管理系统打包脚本 (Windows)

echo ========================================
echo 合同管理系统打包工具 (轻量版)
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 安装PyInstaller
echo [1/3] 安装PyInstaller...
pip install pyinstaller

REM 清理旧的构建文件
echo [2/3] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec

REM 打包
echo [3/3] 开始打包...
pyinstaller --onefile --windowed --name "合同管理系统" main.py

REM 检查打包结果
if exist "dist\合同管理系统.exe" (
    echo.
    echo ========================================
    echo 打包成功！
    echo 可执行文件位置: dist\合同管理系统.exe
    for %%I in (dist\合同管理系统.exe) do echo 文件大小: %%~zI 字节
    echo ========================================
) else (
    echo.
    echo [错误] 打包失败，请检查错误信息
)

pause
