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

## Credentials

### AdBot Database URL

postgres://ad_bot:ppgereok8e0vZFP@ad-bot-db.fly.dev:5432/ad_bot?sslmode=disable

### Main Database URL

postgres://postgres:uO8AVurHacxBvet@[fdaa:1:6c69:0:1::4]:5432

### Other Credentials

ADBOT_API_HASH=3c2a25a9c380673b4a9563cd2501fc23
ADBOT_API_ID=4277770
ADBOT_TOKEN=5334726164:AAFfkU30-Ww00tK10l_An9vAN9hJzhLssKI
LOGGING=INFO
TZ=Europe/Kiev
