FROM debian:13-slim

# Install pyenv build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git gpg ca-certificates \
    libbz2-dev libffi-dev liblzma-dev libncursesw5-dev \
    libreadline-dev libsqlite3-dev libssl-dev \
    libxml2-dev libxmlsec1-dev tk-dev xz-utils zlib1g-dev \
    ripgrep fd-find jq diffstat shellcheck \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (for JS/TS repo analysis)
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create astra user (UID 1000)
RUN useradd -m -u 1000 -s /bin/bash astra

# Switch to astra user for pyenv + Python install
USER astra
WORKDIR /home/astra

ENV PYENV_ROOT="/home/astra/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"

RUN git clone --depth 1 --branch v2.6.27 https://github.com/pyenv/pyenv.git "$PYENV_ROOT" \
    && pyenv install 3.13.12 \
    && pyenv global 3.13.12 \
    && pip install --upgrade pip \
    && pip install ruff mypy bandit semgrep invoke

# Install poetry and project dependencies (before src copy for caching)
WORKDIR /home/astra/astra-job
COPY --chown=astra:astra shared/ /home/astra/shared/
COPY --chown=astra:astra job/pyproject.toml job/poetry.lock ./
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root --no-directory

# Generate available-binaries manifest
RUN printf '%s\n' \
    "## Available binaries" \
    "" \
    "These binaries are available:" \
    "" \
    "- \`bandit\` — Python security vulnerability scanner" \
    "- \`diffstat\` — summarize diffs (files changed, insertions, deletions)" \
    "- \`fdfind\` (fd) — fast file finder by name/pattern" \
    "- \`gh\` — GitHub CLI: PR details, comments, checks, API calls" \
    "- \`git\` — version control: diff, blame, log, branch operations" \
    "- \`invoke\` (inv) — Python task runner for project automation" \
    "- \`jq\` — JSON parsing and transformation" \
    "- \`mypy\` — Python static type checker" \
    "- \`node\`, \`npm\`, \`npx\` — run JS/TS tools (e.g. \`npx tsc --noEmit\`, \`npx eslint\`)" \
    "- \`poetry\` — Python dependency manager and virtual environments" \
    "- \`pyenv\` — Python version manager (install/switch Python versions)" \
    "- \`python3\`, \`pip\` — Python interpreter and package manager" \
    "- \`rg\` (ripgrep) — fast regex search across files" \
    "- \`ruff\` — fast Python linter and formatter" \
    "- \`semgrep\` — multi-language static analysis and security patterns" \
    "- \`shellcheck\` — static analysis for shell scripts" \
    > /home/astra/available-binaries.md

# Copy source and install project
COPY --chown=astra:astra job/src/ ./src/
RUN poetry install && pyenv rehash

ENTRYPOINT ["astra"]
