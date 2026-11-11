SELECT 'CREATE DATABASE aibrand_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aibrand_test')\gexec
