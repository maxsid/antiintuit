# AntiIntuit
(**I'm against cheating and excuse me for this project. Study hard.**)

AntiIntuit is a system that solves tests on website [intuit.ru](https://intuit.ru) and stores results in database.
AntiIntuit contains of the some components:
- Accounts Manager - registers and deletes accounts
- Courses Manager - checks courses 
- Tests Manager - checks tests and appoints tests to accounts
- Tests Solver - solves tests
- Session Manager - solves the problem of database collisions
- Database API
- Telegram Bot - gives tests results to users by Telegram

This project is using *Python 3.7.4*, *Docker* and *Kubernetes*.
## How to run
### docker
Firstly, you have to build the docker images and push them in your images repository because mine is private.
You can do it by executing `build.sh <repository_name>`, for instance:
```bash
./build.sh maxsid/antiintuit
```
### kubernetes
In yaml files specified *'antiintuit'* namespace (see also ENV in Tests Solver yaml file). 

Field image has images from my repository with **imagePullSecrets**. You should change these fields. 

Also, you can create GrayLog server and create *graylog-config* ConfigMap:
```bash
kubectl create configmap graylog-config --from-literal="HOST=<host-to-graylog-server>"
```

Now run the next commands:
```bash
# secret with database data. Change NAME, USER, PASSWORD
kubectl create secret generic database-secret --from-literal="DATABASE_TYPE=mysql" \ 
    --from-literal="DATABASE_HOST=mariadb" --from-literal="DATABASE_NAME=<database-name>" \ 
    --from-literal="DATABASE_USER=<user>" --from-literal="DATABASE_PASSWORD=<password>"
# create MariaDB deploy
kubectl create -f kubernetes/mariadb/
# create tables in database
kubectl create -f kubernetes/antiintuit/jobs/database-init-job.yaml
# create PersistentVolumeClaim for the image storage:
kubectl create -f kubernetes/antiintuit/pvc/
# create all Cronjobs with Accounts Manager, Courses Manager and Tests Manager 
kubectl create -f kubernetes/antiintuit/cronjobs
# create Session Manager
kubectl create -f kubernetes/session-manager
# create Tests Solver
kubectl create -f kubernetes/antiintuit/endless-tests-solver
# create API
kubectl create -f kubernetes/antiintuit/api/
# create Telegram Bot with Redis storage
kubectl create -f kubernetes/tbot/redis
kubectl secret generic tbot-token --from-literal="token=<telegram-bot-token>"
kubectl create -f kubernetes/tbot/tbot
```

Database can fill out too long, but you already can use Telegram Bot