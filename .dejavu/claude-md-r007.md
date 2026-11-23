<!-- dejavu rule: r007 | signature: Bash:sed:macos_flag -->

When calling Bash (command matches 'sed -i '): On macOS, sed -i requires an empty string argument: use `sed -i '' 's/find/replace/' file`, not `sed -i 's/find/replace/' file`. Omitting the empty string causes exit code 1.
