#!/bin/sh
# Forced command for the iPhone's SSH key (see OPERATING.md): the key can only run these two actions.
case "$SSH_ORIGINAL_COMMAND" in
  shutdown)
    sudo -n /sbin/shutdown -h +1
    ;;
  cancel)
    sudo -n /sbin/shutdown -c
    ;;
  *)
    echo "usage: shutdown | cancel" >&2
    exit 1
    ;;
esac
