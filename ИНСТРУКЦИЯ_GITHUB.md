# Как повторно загрузить проект на GitHub

Эта памятка описывает обновление проекта `analitika_magazina` и создание нового репозитория для другого проекта. Команды приведены для Windows PowerShell.

## Что уже опубликовано

В репозитории [analitika_magazina](https://github.com/Igor-petrenko5/analitika_magazina) уже лежат Python-пайплайн, DAG Airflow, SQL-запросы, инструкция запуска, Excel-метрики и HTML-отчёт.

Исходный CSV и построчная SQLite-база не загружены в публичный репозиторий: там хранятся события на уровне пользователей. Файл `.gitignore` защищает от их случайной отправки. Не удаляйте строки `data/DZ_user_actions.csv` и `output/analytics.db` из этого файла, если репозиторий остаётся публичным.

## Один раз: получить проект на компьютер

1. Установите Git for Windows, если команда `git` ещё не работает.
2. Откройте PowerShell и выполните:

```powershell
cd C:\
git clone https://github.com/Igor-petrenko5/analitika_magazina.git analytics_shop_github
cd C:\analytics_shop_github
```

`git clone` создаёт локальную копию репозитория. Работайте далее в этой копии. Не клонируйте поверх существующей папки `C:\analytics_shop`.

3. Скопируйте исходный CSV в папку `data` (если он сохранён в старой папке):

```powershell
Copy-Item C:\analytics_shop\data\DZ_user_actions.csv .\data\DZ_user_actions.csv
```

CSV останется только на компьютере благодаря `.gitignore`.

## Повторный расчёт

В папке `C:\analytics_shop_github` активируйте своё виртуальное окружение или создайте новое:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/pipeline.py --input data/DZ_user_actions.csv --output output
```

Пайплайн обновит Excel и HTML. SQLite-база создастся локально, но не попадёт в публичный репозиторий.

## Отправить изменения в существующий репозиторий

Сначала получите последние изменения и убедитесь, что находитесь в папке проекта:

```powershell
cd C:\analytics_shop_github
git pull origin main
git status --short
```

`git status` показывает изменённые и новые файлы. Затем добавьте изменения, ещё раз проверьте список и сохраните их в Git:

```powershell
git add -A
git status --short
git diff --cached --stat
git commit -m "Обновить расчёты и отчёты"
git push origin main
```

`git add -A` подготавливает изменения, `git commit` сохраняет их локально, `git push` отправляет их на GitHub. До `commit` и `push` проверьте, что `data/DZ_user_actions.csv`, `output/analytics.db`, `.venv` и `output/airflow.db` не появились в подготовленном списке. Если появились, остановитесь и проверьте `.gitignore`.

При первом `git push` Git может открыть окно входа GitHub. Войдите в свой аккаунт в браузере; пароль и коды подтверждения вводите только на странице GitHub.

## Создать отдельный новый репозиторий

1. На GitHub нажмите **New repository**, задайте имя и выберите видимость. Для учебной сдачи обычно удобен **Public**, но помните: все опубликованные файлы сможет скачать любой человек. **Private** ограничивает доступ участниками, которым вы его предоставите.
2. Для простого первого `push` создайте пустой репозиторий без добавления README, `.gitignore` и лицензии на сайте.
3. В PowerShell перейдите в папку проекта и выполните:

```powershell
cd C:\путь\к\папке_проекта
git init -b main
git add -A
git status --short
git diff --cached --stat
git commit -m "Добавить учебный проект"
git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПОЗИТОРИЯ.git
git push -u origin main
```

Перед отправкой внимательно проверьте `git status`: не добавляйте пароли, ключи, `.env`, виртуальное окружение, логи, локальные базы с построчными событиями или исходные данные, если репозиторий открыт всем.

## Если команда сообщает об ошибке

- `git is not recognized` — установите Git for Windows и откройте новое окно PowerShell.
- `rejected` или `fetch first` — сначала выполните `git pull origin main`, разрешите возможные конфликты, затем повторите `git push`.
- `nothing to commit` — изменений нет; проверьте, сохранили ли вы файл.
- Если GitHub отклонил большой или чувствительный файл, не переименовывайте его ради обхода проверки. Проверьте его содержимое и правила доступа к репозиторию.

