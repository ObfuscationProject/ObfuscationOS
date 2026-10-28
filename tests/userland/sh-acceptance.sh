# POSIX sh acceptance for the static musl userland (ports/busybox, decision 0004).
# Run in the guest as `sh /usr/share/userland-tests/sh-acceptance.sh`. Every
# check prints one OK_MUSL_SH_CHECK line; the run ends with one
# OK_MUSL_SH scope=hardware ... line, or OK_MUSL_SH_FAIL with the failed check.
# The scratch directory under /tmp is removed on success.

failed=
check() {
    name=$1 expected=$2 actual=$3
    if [ "$expected" = "$actual" ]; then
        echo "OK_MUSL_SH_CHECK $name=pass"
    else
        echo "OK_MUSL_SH_CHECK $name=FAIL expected=[$expected] actual=[$actual]"
        failed="$failed $name"
    fi
}

work=/tmp/musl-sh.$$
rm -rf "$work" && mkdir "$work" && cd "$work" || { echo "OK_MUSL_SH_FAIL setup"; exit 1; }

# Parameter, arithmetic, command and field expansion.
word="musl shell"
set -- first "second arg" third
check parameters "3:second arg:musl" "$#:$2:${word%% *}"
check defaults "fallback:set" "${unset_name:-fallback}:${word:+set}"
check lengths "10:5" "${#word}:$(( ${#word} / 2 ))"
check arithmetic "42:7:1" "$(( 6 * 7 )):$(( (1 << 3) - 1 )):$(( 3 > 2 ))"
check substitution "a-b-c" "$(echo a b c | tr ' ' -)"
check nested "abc" "$(printf '%s' "$(echo a)$(echo b)")c"
count=0
for field in $word; do count=$((count + 1)); done
check fields "2" "$count"
IFS=: read -r left right <<END
alpha:beta
END
check ifs "beta-alpha" "$right-$left"
check quoting '$word "x" \' "\$word \"x\" \\"

# Globbing over files this script created.
: > g1.txt; : > g2.txt; : > other.log
set -- g*.txt
check glob "g1.txt g2.txt" "$*"
set -- nomatch*.none
check glob_literal "nomatch*.none" "$1"

# Pipelines, exit status and negation.
check pipeline "3" "$(printf 'x\ny\nz\n' | wc -l | tr -d ' ')"
check pipeline_long "C" "$(echo abc | cut -c3 | tr a-z A-Z | sed 's/^/ /' | awk '{print $1}')"
false | true
check pipe_status "0" "$?"
! false
check negation "0" "$?"

# Redirection.
echo one > out.txt
echo two >> out.txt
check redirect_append "one two" "$(cat out.txt | tr '\n' ' ' | sed 's/ $//')"
check redirect_input "2" "$(wc -l < out.txt | tr -d ' ')"
{ echo to-stderr >&2; } 2> err.txt
check redirect_stderr "to-stderr" "$(cat err.txt)"
check redirect_dup "both" "$( { echo both 1>&2; } 2>&1 )"
exec 3> fd3.txt
echo via-fd3 >&3
exec 3>&-
check redirect_fd "via-fd3" "$(cat fd3.txt)"
cat > heredoc.txt <<EOT
line $word
EOT
check heredoc "line musl shell" "$(cat heredoc.txt)"
cat > quoted.txt <<'EOT'
$word
EOT
check heredoc_quoted '$word' "$(cat quoted.txt)"
set -C
( echo clobber > out.txt ) 2>/dev/null
check noclobber "refused" "$([ $? -ne 0 ] && echo refused)"
set +C

# Command lists, compound commands and functions.
r=; true && r="${r}a"; false && r="${r}b"; false || r="${r}c"; true; r="${r}d"
check lists "acd" "$r"
check subshell "outer" "$(x=outer; (x=inner); echo "$x")"
group=; { group=set; }
check group "set" "$group"
total=0; i=1
while [ "$i" -le 5 ]; do total=$((total + i)); i=$((i + 1)); done
check while "15" "$total"
case "file.tar.gz" in *.gz) kind=gzip ;; *) kind=other ;; esac
check case "gzip" "$kind"
square() { echo $(( $1 * $1 )); }
check function "49" "$(square 7)"
scoped() { set -- inner; echo "$1"; }
set -- outer
check function_args "inner:outer" "$(scoped):$1"
check background "done" "$(sleep 0 & wait; echo done)"
check trap "trapped" "$(trap 'echo trapped' EXIT; true)"
check exit_status "3" "$(sh -c 'exit 3'; echo $?)"
check command_v "path" "$(case $(command -v cat) in /*/cat) echo path ;; esac)"
check eval "6" "$(eval 'echo $((1 + 2 + 3))')"

# execve: long argument and environment lists, #! scripts and the ENOEXEC
# fallback of a plain executable text file.
set -- $(seq 1 400)
check exec_args "400:400" "$(sh -c 'echo $#:${400}' sh "$@")"
long=$(printf '%010000d' 0)
check exec_env "10000" "$(LONG=$long sh -c 'echo ${#LONG}')"
printf '#!/bin/sh\necho "script:$1"\n' > script.sh && chmod +x script.sh
check exec_script "script:arg" "$(./script.sh arg)"
printf 'echo plain:$1\n' > plain.sh && chmod +x plain.sh
check exec_enoexec "plain:arg" "$(./plain.sh arg)"

# Kernel character devices on /dev.
check dev_null "0:yes" "$(echo discarded > /dev/null; wc -c < /dev/null | tr -d ' '):$([ -c /dev/null ] && echo yes)"
check dev_zero "512" "$(head -c 512 /dev/zero | wc -c | tr -d ' ')"
check dev_full "fails" "$(echo x 2>/dev/null > /dev/full || echo fails)"

# Linux uname, sysinfo, link, symlink and chown.
check uname "Linux" "$(uname -s)"
check uptime "up" "$(uptime | sed -n 's/.* \(up\) .*/\1/p')"
check hostname "named" "$([ -n "$(hostname)" ] && echo named)"
echo a > linked && ln linked hard && echo b >> hard && ln -s hard soft
check links "a b:symlink" "$(cat linked | tr '\n' ' ' | sed 's/ $//'):$([ -L soft ] && echo symlink)"
if [ "$(id -u)" = 0 ]; then
    check chown "7:8" "$(chown 7:8 linked && ls -n linked | awk '{print $3":"$4}')"
else
    check chown "refused" "$(chown 7:8 linked 2>/dev/null || echo refused)"
fi

# Applets whose images put ELF metadata past the former admission prefix.
check bc "18446744073709551616:5" "$(echo '2^64' | bc):$(echo '2 3 + p' | dc)"
check bzip2 "round" "$(echo round | bzip2 | bunzip2)"

# A directory listing spans more than one 64-entry provider page.
mkdir listed && i=0 && while [ $i -lt 66 ] && : > "listed/f$i"; do i=$((i + 1)); done
check listing "66:66" "$i:$(ls listed | wc -l | tr -d ' ')"
check listing_glob "66" "$(set -- listed/*; echo $#)"

cd / && rm -rf "$work"
if [ -n "$failed" ]; then
    echo "OK_MUSL_SH_FAIL checks=$failed"
    exit 1
fi
echo "OK_MUSL_SH scope=hardware expansion=pass pipelines=pass redirection=pass lists=pass functions=pass"
