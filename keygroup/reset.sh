# KEY GROUP portal - set a new admin password (asks you to type it)
set -u
docker ps --format '{{.Names}}' | grep -qx kg-portal || { echo "STOP: kg-portal is not running"; exit 1; }
while true; do
  printf 'New admin password (min 8 chars): ' > /dev/tty; read -r P1 < /dev/tty
  [ ${#P1} -ge 8 ] || { echo "Too short, try again"; continue; }
  break
done
docker exec -e NEWPW="$P1" kg-portal python -c "
import os, app
pw = os.environ['NEWPW']; ph = app.norm_phone(os.environ.get('ADMIN_PHONE','577114118'))
con = app.db()
n = con.execute(\"UPDATE users SET pw=?, blocked=0, totp_on=0 WHERE phone=? AND role='admin'\", (app.hash_pw(pw), ph)).rowcount
con.commit(); con.close()
print('DONE - admin password changed. Login phone: 577114118' if n else 'PROBLEM - admin user not found')
"
