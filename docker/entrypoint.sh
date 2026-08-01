#!/bin/bash
set -e

# build prefix
CHATGPT_ON_WECHAT_PREFIX=${CHATGPT_ON_WECHAT_PREFIX:-""}
# path to config.json
CHATGPT_ON_WECHAT_CONFIG_PATH=${CHATGPT_ON_WECHAT_CONFIG_PATH:-""}
# execution command line
CHATGPT_ON_WECHAT_EXEC=${CHATGPT_ON_WECHAT_EXEC:-""}
# writable config and private runtime data
LIGHTAGENT_DATA_DIR=${LIGHTAGENT_DATA_DIR:-"/home/agent/.lightagent"}
export LIGHTAGENT_DATA_DIR
IMAGE_OUTPUT_DIR=${IMAGE_OUTPUT_DIR:-"/home/agent/lightagent/images"}
export IMAGE_OUTPUT_DIR
AUTO_WEB_PASSWORD_SENTINEL="__LIGHTAGENT_AUTO_GENERATE__"

# use environment variables to pass parameters
# if you have not defined environment variables, set them below
# export OPEN_AI_API_KEY=${OPEN_AI_API_KEY:-'YOUR API KEY'}
# export OPEN_AI_PROXY=${OPEN_AI_PROXY:-""}
# export SINGLE_CHAT_PREFIX=${SINGLE_CHAT_PREFIX:-'["bot", "@bot"]'}
# export SINGLE_CHAT_REPLY_PREFIX=${SINGLE_CHAT_REPLY_PREFIX:-'"[bot] "'}
# export GROUP_CHAT_PREFIX=${GROUP_CHAT_PREFIX:-'["@bot"]'}
# export GROUP_NAME_WHITE_LIST=${GROUP_NAME_WHITE_LIST:-'["ChatGPT测试群", "ChatGPT测试群2"]'}
# export IMAGE_CREATE_PREFIX=${IMAGE_CREATE_PREFIX:-'["画", "看", "找"]'}
# export CONVERSATION_MAX_TOKENS=${CONVERSATION_MAX_TOKENS:-"1000"}
# export SPEECH_RECOGNITION=${SPEECH_RECOGNITION:-"False"}
# export CHARACTER_DESC=${CHARACTER_DESC:-"你是ChatGPT, 一个由OpenAI训练的大型语言模型, 你旨在回答并解决人们的任何问题，并且可以使用多种语言与人交流。"}
# export EXPIRES_IN_SECONDS=${EXPIRES_IN_SECONDS:-"3600"}

# CHATGPT_ON_WECHAT_PREFIX is empty, use /app
if [ "$CHATGPT_ON_WECHAT_PREFIX" == "" ] ; then
    CHATGPT_ON_WECHAT_PREFIX=/app
fi

# CHATGPT_ON_WECHAT_CONFIG_PATH is empty, use '/app/config.json'
if [ "$CHATGPT_ON_WECHAT_CONFIG_PATH" == "" ] ; then
    CHATGPT_ON_WECHAT_CONFIG_PATH=$CHATGPT_ON_WECHAT_PREFIX/config.json
fi

# CHATGPT_ON_WECHAT_EXEC is empty, use ‘python app.py’
if [ "$CHATGPT_ON_WECHAT_EXEC" == "" ] ; then
    CHATGPT_ON_WECHAT_EXEC="python app.py"
fi

# modify content in config.json
# if [ "$OPEN_AI_API_KEY" == "YOUR API KEY" ] || [ "$OPEN_AI_API_KEY" == "" ]; then
#     echo -e "\033[31m[Warning] You need to set OPEN_AI_API_KEY before running!\033[0m"
# fi


ensure_web_password() {
    if [ "${WEB_PASSWORD:-$AUTO_WEB_PASSWORD_SENTINEL}" != "$AUTO_WEB_PASSWORD_SENTINEL" ]; then
        echo "[LightAgent] Web console password is provided by WEB_PASSWORD (value hidden)"
        return
    fi

    unset WEB_PASSWORD
    managed_password="$(
        /usr/local/bin/python - "$LIGHTAGENT_DATA_DIR/config.json" <<'PY'
import json
import secrets
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as file:
    config = json.load(file)

password = str(config.get("web_password") or "")
if not password:
    password = secrets.token_urlsafe(18)
    config["web_password"] = password
    with open(path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)
        file.write("\n")

print(password)
PY
    )"
    echo "[LightAgent] Web console password: $managed_password"
    echo "[LightAgent] Password is persisted in $LIGHTAGENT_DATA_DIR/config.json"
}

prepare_runtime_dirs() {
    mkdir -p "$LIGHTAGENT_DATA_DIR" /home/agent/lightagent "$IMAGE_OUTPUT_DIR"
    if [ ! -f "$LIGHTAGENT_DATA_DIR/config.json" ]; then
        cp "$CHATGPT_ON_WECHAT_PREFIX/config-template.json" \
           "$LIGHTAGENT_DATA_DIR/config.json"
    fi
    ensure_web_password
}

# Initialize mounted volumes, then drop to the non-root user.
if [ "$(id -u)" = "0" ]; then
    prepare_runtime_dirs
    chown agent:agent \
        "$LIGHTAGENT_DATA_DIR" \
        "$LIGHTAGENT_DATA_DIR/config.json" \
        /home/agent/lightagent \
        "$IMAGE_OUTPUT_DIR"
    exec su agent -s /bin/bash -c \
        "python /app/scripts/seed_project_knowledge.py --workspace /home/agent/lightagent --app-root /app && cd $CHATGPT_ON_WECHAT_PREFIX && exec $CHATGPT_ON_WECHAT_EXEC"
fi

# Fallback for images started directly as the agent user.
prepare_runtime_dirs
python /app/scripts/seed_project_knowledge.py --workspace /home/agent/lightagent --app-root /app
cd "$CHATGPT_ON_WECHAT_PREFIX"
exec $CHATGPT_ON_WECHAT_EXEC


