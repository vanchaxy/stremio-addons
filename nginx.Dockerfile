FROM  nginx:1.24.0

COPY ./nginx.conf /etc/nginx/conf.d/default.conf
