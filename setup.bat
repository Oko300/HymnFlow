@echo off
echo ========================================
echo  HymnFlow — First Time Setup (Windows)
echo ========================================

echo.
echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo [2/4] Creating .env file from template...
if not exist .env (
    copy .env.example .env
    echo .env file created. Open it and fill in your API keys.
) else (
    echo .env already exists — skipping.
)

echo.
echo [3/4] Creating fonts directory...
if not exist fonts mkdir fonts
echo Fonts folder ready.
echo Download these two fonts and place them in /fonts:
echo   - Cinzel-Regular.ttf   (from Google Fonts: fonts.google.com/specimen/Cinzel)
echo   - Lato-Italic.ttf      (from Google Fonts: fonts.google.com/specimen/Lato)

echo.
echo [4/4] Creating music directory...
if not exist music mkdir music
echo Music folder ready.
echo Download 30-50 worship instrumentals from pixabay.com/music
echo Search: worship, gospel piano, hymn instrumental, devotional
echo Save all .mp3 files into the /music folder.

echo.
echo ========================================
echo  Setup complete!
echo  Next steps:
echo  1. Fill in your .env file with real API keys
echo  2. Add fonts to /fonts folder
echo  3. Add music tracks to /music folder
echo  4. Run: python test_sprint1.py
echo ========================================
pause
