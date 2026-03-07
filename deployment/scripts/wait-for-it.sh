#!/bin/bash
# wait-for-it.sh — wait until a TCP host:port is available
# Usage: wait-for-it.sh host:port [-t timeout] [-- command args]

WAITFORIT_cmdname=$(basename "$0")
echoerr() { if [[ $WAITFORIT_QUIET -ne 1 ]]; then echo "$@" 1>&2; fi }

usage() {
    cat << USAGE >&2
Usage:
    $WAITFORIT_cmdname host:port [-s] [-t timeout] [-- command args]
    -h HOST | --host=HOST     Host or IP under test
    -p PORT | --port=PORT     TCP port under test
    -s | --strict             Only execute subcommand if the test succeeds
    -q | --quiet              Don't output any status messages
    -t TIMEOUT | --timeout=TIMEOUT  Timeout in seconds (default 15)
    -- COMMAND ARGS           Execute command with args after the test finishes
USAGE
    exit 1
}

wait_for() {
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        echoerr "$WAITFORIT_cmdname: waiting $WAITFORIT_TIMEOUT seconds for $WAITFORIT_HOST:$WAITFORIT_PORT"
    else
        echoerr "$WAITFORIT_cmdname: waiting for $WAITFORIT_HOST:$WAITFORIT_PORT without a timeout"
    fi
    WAITFORIT_start_ts=$(date +%s)
    while :; do
        (echo -n > /dev/tcp/$WAITFORIT_HOST/$WAITFORIT_PORT) >/dev/null 2>&1
        WAITFORIT_result=$?
        if [[ $WAITFORIT_result -eq 0 ]]; then
            WAITFORIT_end_ts=$(date +%s)
            echoerr "$WAITFORIT_cmdname: $WAITFORIT_HOST:$WAITFORIT_PORT is available after $((WAITFORIT_end_ts - WAITFORIT_start_ts)) seconds"
            break
        fi
        sleep 1
        WAITFORIT_now_ts=$(date +%s)
        if [[ $WAITFORIT_TIMEOUT -gt 0 && $((WAITFORIT_now_ts - WAITFORIT_start_ts)) -ge $WAITFORIT_TIMEOUT ]]; then
            echoerr "$WAITFORIT_cmdname: timeout waiting for $WAITFORIT_HOST:$WAITFORIT_PORT"
            return 1
        fi
    done
    return 0
}

WAITFORIT_TIMEOUT=15
WAITFORIT_STRICT=0
WAITFORIT_QUIET=0
WAITFORIT_CLI=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        *:* ) WAITFORIT_HOST=$(echo "$1" | cut -d: -f1); WAITFORIT_PORT=$(echo "$1" | cut -d: -f2); shift;;
        -h|--host) WAITFORIT_HOST="$2"; shift 2;;
        -p|--port) WAITFORIT_PORT="$2"; shift 2;;
        -t|--timeout) WAITFORIT_TIMEOUT="$2"; shift 2;;
        -s|--strict) WAITFORIT_STRICT=1; shift;;
        -q|--quiet) WAITFORIT_QUIET=1; shift;;
        --) shift; WAITFORIT_CLI=("$@"); break;;
        --help) usage;;
        *) echoerr "Unknown argument: $1"; usage;;
    esac
done

if [[ -z "$WAITFORIT_HOST" || -z "$WAITFORIT_PORT" ]]; then
    echoerr "Error: you need to provide a host and port to test."
    usage
fi

wait_for
WAITFORIT_RESULT=$?

if [[ ${#WAITFORIT_CLI[@]} -gt 0 ]]; then
    if [[ $WAITFORIT_RESULT -ne 0 && $WAITFORIT_STRICT -eq 1 ]]; then
        echoerr "$WAITFORIT_cmdname: strict mode, refusing to execute subprocess"
        exit $WAITFORIT_RESULT
    fi
    exec "${WAITFORIT_CLI[@]}"
else
    exit $WAITFORIT_RESULT
fi
