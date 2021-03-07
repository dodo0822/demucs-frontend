from environs import Env

env = Env()
env.read_env()

db_host = env.str('DB_HOST', 'localhost')
db_port = env.int('DB_PORT', 27017)