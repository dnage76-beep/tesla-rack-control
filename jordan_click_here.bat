@echo off
set /p com_port=Enter your COM Port (Example: COM8): 
python tesla_control_rc.py --rc-port %com_port%
pause