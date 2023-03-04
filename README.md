# ADBOT

## Setup DB

```sql
postgres=# \c ad_bot
You are now connected to database "ad_bot" as user "postgres".
ad_bot=# UPDATE users set role = 'ADMIN';
UPDATE 1
ad_bot=# INSERT INTO subscriptions VALUES (interval '999 days', 'Test');
INSERT 0 1
ad_bot=# INSERT into categories values (1,NULL, 'Эскорт');
INSERT 0 1
ad_bot=# UPDATE chats set period= interval '1 hours';
UPDATE 63
ad_bot=#
```

## Import Database

### Setup Proxy

fly proxy 15432:5432 --app ad-bot-db

## Credentials

### Main Database URL

postgres://postgres:TmmonCDUvKuUA8w@[fdaa:1:6c69:0:1::a]:5432

### AdBot Database URL

DATABASE_URL=postgres://ad_bot:LISuyHnCGbrLI79@[fdaa:1:6c69:0:1::a]:5432/ad_bot?sslmode=disable

### Other Credentials

ADBOT_API_HASH=3c2a25a9c380673b4a9563cd2501fc23
ADBOT_API_ID=4277770
ADBOT_TOKEN=5334726164:AAFfkU30-Ww00tK10l_An9vAN9hJzhLssKI
LOGGING=INFO
TZ=Europe/Kiev
