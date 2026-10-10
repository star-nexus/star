#!/bin/bash
# Native dependencies belong to ENV only; explicit Python remains available.
env_backend=rust
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
    case "${args[$i]}" in
        --backend) env_backend="${args[$((i+1))]}" ;;
        --backend=*) env_backend="${args[$i]#--backend=}" ;;
    esac
done
if [[ "$env_backend" == rust ]]; then
    exec uv run --extra native rotk_env/main.py "$@"
fi
exec uv run rotk_env/main.py "$@"
