FROM python:3.9
WORKDIR opt/
RUN pip install poetry
COPY poetry.lock ./
COPY pyproject.toml ./
RUN poetry install
COPY . ./
CMD ["poetry", "run", "waitress-serve", "'--listen=*:8080'", "main:app"]
