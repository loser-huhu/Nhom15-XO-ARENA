# Sử dụng Python 3.9 nhẹ
FROM python:3.9-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Copy toàn bộ code vào
COPY . .

# Cài đặt thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Mở cổng 10000 (Cổng mặc định của Render)
EXPOSE 10000

# LỆNH KHỞI ĐỘNG QUAN TRỌNG (Gunicorn + Gevent)
CMD ["gunicorn", "-k", "gevent", "-w", "1", "-b", "0.0.0.0:10000", "app:app"]