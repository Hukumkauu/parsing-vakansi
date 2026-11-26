@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Мониторинг зарплат

echo ============================================
echo   Мониторинг уровня заработных плат
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python не найден.
    echo Установите Python 3.12 с сайта https://www.python.org/downloads/
    echo При установке обязательно поставьте галочку "Add python.exe to PATH",
    echo затем запустите этот файл снова.
    echo.
    pause
    exit /b 1
)

echo [1/4] Проверка библиотек...
python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo Не удалось установить библиотеки. Проверьте подключение к интернету.
    pause
    exit /b 1
)

echo [2/4] Проверка ключа SuperJob...
if "%SUPERJOB_KEY%"=="" (
    echo.
    echo Ключ SuperJob не найден. Без него вакансии берутся только с "Работы России".
    echo Бесплатный ключ: https://api.superjob.ru/register  поле Secret key
    set "KEY="
    set /p "KEY=Вставьте ключ правой кнопкой мыши и нажмите Enter (или просто Enter, чтобы пропустить): "
    if not "!KEY!"=="" (
        setx SUPERJOB_KEY "!KEY!" >nul
        set "SUPERJOB_KEY=!KEY!"
        echo Ключ сохранён.
    )
    echo.
)

echo [3/4] Проверка файла настроек...
if not exist "Мониторинг зарплат.xlsx" (
    python main.py init
    echo Создан файл с примером настроек. Должности, локации и вилки банка
    echo можно поменять в нём и запустить мониторинг снова.
    echo.
)

echo [4/4] Сбор данных и расчёт. Это займёт несколько минут...
echo Если файл "Мониторинг зарплат.xlsx" открыт в Excel - закройте его.
echo.
python main.py run --open
if errorlevel 1 (
    echo.
    echo Отчёт не обновлён, причина написана выше.
) else (
    echo.
    echo Готово. Отчёт открыт в Excel.
)
echo.
pause
