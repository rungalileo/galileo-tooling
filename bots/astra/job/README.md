# Astra Job Runner

Test in a container:

```shell
docker build -t astra-job . && docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e GITHUB_TOKEN=$GITHUB_TOKEN \
  -e SHORTCUT_API_TOKEN=$SHORTCUT_API_TOKEN \
  -v "$(pwd)/.output:/home/astra/astra-job/.output" \
  --workdir /home/astra/astra-job \
  astra-job poetry run astra review <PR url>
```
