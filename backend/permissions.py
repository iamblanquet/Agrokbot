"""Server-side administrator authorization shared by login and API checks."""
def administrator(db, user, owner):
    account=db.execute('SELECT active FROM app_users WHERE username=?',(user,)).fetchone()
    if account is None:
        return user==owner
    return bool(account['active'] and db.execute('SELECT 1 FROM administrators WHERE user=?',(user,)).fetchone())
