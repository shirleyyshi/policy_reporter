@echo off
REM Windows 任务计划脚本（本地开发用）
REM 用法：
REM   1. 打开"任务计划程序"
REM   2. 创建基本任务，触发器选每天 07:00
REM   3. 操作选"启动程序"，程序路径指向本脚本
REM   4. 起始目录设为项目根目录

cd /d "%~dp0\.."

echo [%date% %time%] 开始爬取...
python backend\manage.py crawl_policies --all

echo [%date% %time%] 重建 RAG 索引...
python backend\manage.py build_index

echo [%date% %time%] 完成
