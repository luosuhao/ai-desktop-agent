# Image Model Configuration

Use this reference only when the local API/CLI fallback is needed and the runtime config is missing or must be changed.

Do not manually parse `.env`. The fallback CLI loads the shared config automatically. Run the fallback command first, then use this document only if the CLI reports missing or invalid configuration.

Ask the user to configure or update settings only when:

- The fallback CLI reports missing `OPENAI_API_KEY`.
- The user explicitly wants to change API key, base URL, or model.
- A real API call fails with authentication, permission, base URL, or model-not-found errors.

## When Configuration Is Needed

Configure image API access only for API/CLI fallback image generation.

Typical cases:

- Codex is using a third-party API or OpenAI-compatible proxy for image generation.
- The skill is being used from Claude Code, OpenClaw, Hermes Agent, or another agent without Codex's built-in image tool.
- The user explicitly chooses Qwen Image, SiliconFlow, DashScope, AtlasCloud, or another API provider.

If Codex is being used through a GPT subscription and the built-in image tool is available, do not ask the user to configure `gpt-image-2`.
Do not force Qwen Image; it is one optional API fallback provider among several.

## Required And Optional Values

- `OPENAI_API_KEY` is required for real API/CLI fallback calls.
- `OPENAI_BASE_URL` is optional. When it is unset, the CLI uses the official OpenAI API. When it is set, the CLI uses the configured third-party provider base URL.
- `CODEX_PPT_IMAGE_MODEL` is optional. The default is `gpt-image-2`. Use a custom value only when the provider requires one.
- `CODEX_PPT_IMAGE_PROVIDER=qwen-dashscope` selects the DashScope Qwen Image adapter.
- `DASHSCOPE_API_KEY` is required when using Qwen Image through DashScope.
- `DASHSCOPE_BASE_URL` is optional. Leave it unset for the default DashScope `/api/v1` root, or set it to a Model Studio workspace `/api/v1` root.
- `CODEX_PPT_IMAGE_PROVIDER=siliconflow` selects the SiliconFlow image adapter.

Configure provided API settings with `scripts/codex_ppt_runtime.py config --api-key`. The config command writes `~/.codex-ppt-skill/.env`.

## Official OpenAI Example

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --api-key "your-api-key" \
  --model gpt-image-2
```

## OpenAI-Compatible Provider Example

Use this shape for providers that implement the OpenAI Images API paths used by the fallback CLI.

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --api-key "your-provider-api-key" \
  --base-url "https://xxxx.example.com/v1" \
  --model gpt-image-2
```

This produces the same effective runtime config as:

```env
OPENAI_API_KEY=your-provider-api-key
OPENAI_BASE_URL=https://xxxx.example.com/v1
CODEX_PPT_IMAGE_MODEL=gpt-image-2
```

For OpenAI-compatible providers, `OPENAI_BASE_URL` should normally end at the provider's `/v1` root. Do not set it to `/images/generations`, `/images/edits`, or another terminal endpoint. The fallback CLI appends the image-generation or image-edit path through the OpenAI SDK.

Use the provider's model name only when the provider documents a custom name. Otherwise prefer `gpt-image-2`.

## Qwen Image / DashScope Example

Use this optional shape when the user chooses Qwen Image through Alibaba Cloud Model Studio / DashScope. Prefer `qwen-image-2.0-pro` for this route because it supports both text-to-image and image editing.

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --provider qwen-dashscope \
  --dashscope-api-key "your-dashscope-api-key" \
  --model qwen-image-2.0-pro
```

If your account uses a workspace-specific endpoint, set the `/api/v1` root, not the final generation path:

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --provider qwen-dashscope \
  --dashscope-api-key "your-dashscope-api-key" \
  --dashscope-base-url "https://{workspace-id}.cn-beijing.maas.aliyuncs.com/api/v1" \
  --model qwen-image-2.0-pro
```

This produces the same effective runtime config as:

```env
CODEX_PPT_IMAGE_PROVIDER=qwen-dashscope
CODEX_PPT_IMAGE_MODEL=qwen-image-2.0-pro
DASHSCOPE_API_KEY=your-dashscope-api-key
DASHSCOPE_BASE_URL=https://{workspace-id}.cn-beijing.maas.aliyuncs.com/api/v1
```

## Qwen Image / SiliconFlow Example

Use this optional shape when the user chooses SiliconFlow's Qwen Image API. This adapter calls `/v1/images/generations` and downloads the returned image URL immediately.

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --provider siliconflow \
  --api-key "your-siliconflow-api-key" \
  --base-url "https://api.siliconflow.cn/v1" \
  --model "Qwen/Qwen-Image"
```

This produces the same effective runtime config as:

```env
CODEX_PPT_IMAGE_PROVIDER=siliconflow
OPENAI_API_KEY=your-siliconflow-api-key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
CODEX_PPT_IMAGE_MODEL=Qwen/Qwen-Image
```

For generation, `auto` or a 16:9 PPT size is sent as SiliconFlow's recommended `1664x928`. For editing, the adapter automatically maps `Qwen/Qwen-Image` to `Qwen/Qwen-Image-Edit-2509` and omits `image_size`, matching SiliconFlow's Qwen edit API shape.

## AtlasCloud Example

For AtlasCloud, set `--model` to the base model name. The CLI chooses the matching generation or editing model route internally.

```bash
python3 {skill_root}/scripts/codex_ppt_runtime.py config \
  --api-key "your-atlascloud-api-key" \
  --base-url "https://api.atlascloud.ai/api/v1/model" \
  --model openai/gpt-image-2
```

## Runtime Config

The config is written to:

```text
~/.codex-ppt-skill/.env
```

The file is created with mode `0600`. It is shared by Codex, Claude Code, OpenClaw, Hermes Agent, and other local agents.

Process environment variables override `.env` values. A command-line `--model` overrides `CODEX_PPT_IMAGE_MODEL` for that single command.
