"""
Generate a ~4MB test dataset (~1M tokens) for RLM plugin benchmarking.

Creates tests/testbench_1M.json — a realistic server log dataset with:
- 50,000 HTTP request log entries
- Nested JSON with headers, query params, response bodies
- Mixed normal traffic, errors, slow queries, security events
- Realistic patterns that require analysis to find

Test prompts for benchmarking:
1. "Analyze testbench_1M.json — find all 500 errors and group by endpoint"
2. "What are the slowest endpoints? Show p50/p95/p99 latencies"
3. "Find all SQL injection attempts in the query parameters"
4. "Summarize traffic patterns by hour and status code"
5. "Find users with suspicious activity (>100 requests/minute or auth failures)"
"""

import json
import random
import hashlib
import string
import os

random.seed(42)

ENDPOINTS = [
    "/api/users", "/api/users/{id}", "/api/users/{id}/profile",
    "/api/orders", "/api/orders/{id}", "/api/orders/{id}/items",
    "/api/products", "/api/products/{id}", "/api/products/search",
    "/api/auth/login", "/api/auth/logout", "/api/auth/refresh",
    "/api/admin/users", "/api/admin/settings", "/api/admin/logs",
    "/api/payments", "/api/payments/{id}", "/api/payments/webhook",
    "/api/notifications", "/api/notifications/subscribe",
    "/api/reports/daily", "/api/reports/monthly", "/api/reports/export",
    "/api/files/upload", "/api/files/{id}/download",
    "/api/search", "/api/health", "/api/metrics",
]

METHODS = ["GET", "GET", "GET", "GET", "POST", "POST", "PUT", "DELETE", "PATCH"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.2",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15",
    "PostmanRuntime/7.36.0",
    "python-requests/2.31.0",
    "curl/8.4.0",
    "okhttp/4.12.0",
]

IPS = [f"192.168.1.{i}" for i in range(1, 50)] + \
      [f"10.0.{i}.{j}" for i in range(5) for j in range(1, 20)] + \
      ["203.0.113.42", "203.0.113.99", "198.51.100.7"]  # suspicious IPs

USERNAMES = [f"user_{i}" for i in range(200)] + ["admin", "root", "test", "bot_scanner"]

ERROR_MESSAGES = {
    400: ["Invalid request body", "Missing required field: email", "Validation failed: age must be positive",
          "Malformed JSON in request body", "Invalid date format"],
    401: ["Invalid credentials", "Token expired", "Missing authorization header", "Invalid API key"],
    403: ["Insufficient permissions", "Account suspended", "IP blocked", "Rate limit exceeded"],
    404: ["Resource not found", "User not found", "Order not found", "Endpoint not found"],
    500: ["Internal server error", "Database connection failed", "Redis timeout",
          "Null pointer exception in OrderService.processPayment",
          "OutOfMemoryError: Java heap space", "Connection pool exhausted",
          "Deadlock detected in transaction", "Kafka broker unavailable"],
    502: ["Bad gateway", "Upstream service unavailable"],
    503: ["Service temporarily unavailable", "Circuit breaker open for PaymentService"],
}

SQL_INJECTION_PAYLOADS = [
    "1' OR '1'='1", "'; DROP TABLE users; --", "1 UNION SELECT * FROM passwords",
    "admin'--", "1; EXEC xp_cmdshell('dir')", "' OR 1=1 --",
]

RESPONSE_BODIES = {
    "/api/users": lambda: {"users": [{"id": random.randint(1, 9999), "name": rand_name(), "email": rand_email(),
                                       "role": random.choice(["user", "admin", "moderator"]),
                                       "created_at": rand_date(), "last_login": rand_date(),
                                       "settings": {"theme": random.choice(["dark", "light"]),
                                                    "notifications": random.choice([True, False]),
                                                    "language": random.choice(["en", "es", "fr", "de", "ja"])}}
                                      for _ in range(random.randint(5, 20))],
                           "total": random.randint(100, 5000), "page": 1, "per_page": 20},
    "/api/orders": lambda: {"orders": [{"id": f"ORD-{random.randint(10000,99999)}",
                                         "user_id": random.randint(1, 999),
                                         "status": random.choice(["pending", "processing", "shipped", "delivered", "cancelled"]),
                                         "total": round(random.uniform(9.99, 999.99), 2),
                                         "currency": random.choice(["USD", "EUR", "GBP"]),
                                         "items": [{"product_id": random.randint(1, 500),
                                                    "name": rand_product(),
                                                    "quantity": random.randint(1, 5),
                                                    "price": round(random.uniform(4.99, 299.99), 2)}
                                                   for _ in range(random.randint(1, 5))],
                                         "shipping": {"method": random.choice(["standard", "express", "overnight"]),
                                                     "tracking": rand_tracking(),
                                                     "address": rand_address()},
                                         "created_at": rand_date()}
                                        for _ in range(random.randint(3, 10))],
                            "total": random.randint(50, 2000)},
    "/api/products": lambda: {"products": [{"id": random.randint(1, 500),
                                             "name": rand_product(),
                                             "description": rand_description(),
                                             "price": round(random.uniform(4.99, 999.99), 2),
                                             "category": random.choice(["electronics", "clothing", "books", "home", "sports"]),
                                             "tags": random.sample(["sale", "new", "popular", "limited", "eco-friendly", "premium"], k=random.randint(1, 3)),
                                             "inventory": {"warehouse_a": random.randint(0, 500),
                                                          "warehouse_b": random.randint(0, 300),
                                                          "reserved": random.randint(0, 50)},
                                             "reviews": {"average": round(random.uniform(1.0, 5.0), 1),
                                                        "count": random.randint(0, 2000)}}
                                            for _ in range(random.randint(5, 15))]},
}

def rand_name():
    first = random.choice(["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
                            "David", "Elizabeth", "Wei", "Yuki", "Ahmed", "Fatima", "Carlos", "Priya"])
    last = random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                           "Chen", "Tanaka", "Khan", "Patel", "Silva", "Kim", "Mueller", "Dubois"])
    return f"{first} {last}"

def rand_email():
    return f"{''.join(random.choices(string.ascii_lowercase, k=8))}@{random.choice(['gmail.com', 'outlook.com', 'company.io', 'example.org'])}"

def rand_date():
    return f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}Z"

def rand_product():
    adj = random.choice(["Premium", "Classic", "Ultra", "Pro", "Essential", "Deluxe", "Compact", "Smart"])
    noun = random.choice(["Widget", "Gadget", "Device", "Tool", "Kit", "Pack", "Set", "Bundle", "Station", "Hub"])
    return f"{adj} {noun} {random.choice(['X', 'S', 'Pro', 'Plus', 'Max', 'Mini', 'Air', 'SE'])}{random.randint(1,9)}"

def rand_tracking():
    return f"{''.join(random.choices(string.ascii_uppercase, k=2))}{random.randint(100000000, 999999999)}"

def rand_address():
    return {"street": f"{random.randint(1, 9999)} {random.choice(['Main', 'Oak', 'Cedar', 'Elm', 'Park'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Ln'])}",
            "city": random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "London", "Tokyo", "Berlin"]),
            "state": random.choice(["NY", "CA", "IL", "TX", "AZ", "UK", "JP", "DE"]),
            "zip": f"{random.randint(10000, 99999)}",
            "country": random.choice(["US", "US", "US", "UK", "JP", "DE"])}

def rand_description():
    templates = [
        "High-quality {adj} product with {feature}. Perfect for {use}. Made from {material}.",
        "The latest {adj} innovation featuring {feature}. Designed for {use} with {material} construction.",
        "Best-in-class {adj} solution. Includes {feature} and {feature2}. Ideal for {use}.",
    ]
    return random.choice(templates).format(
        adj=random.choice(["durable", "lightweight", "versatile", "innovative", "professional"]),
        feature=random.choice(["wireless connectivity", "AI-powered analytics", "real-time monitoring", "auto-calibration"]),
        feature2=random.choice(["cloud sync", "battery backup", "noise cancellation", "water resistance"]),
        use=random.choice(["daily use", "professionals", "outdoor activities", "home office", "travel"]),
        material=random.choice(["aircraft-grade aluminum", "recycled materials", "premium silicone", "carbon fiber"]),
    )

def generate_entry(idx, ts_hour):
    endpoint = random.choice(ENDPOINTS)
    method = random.choice(METHODS)
    ip = random.choice(IPS)
    username = random.choice(USERNAMES)

    # Determine status code with realistic distribution
    r = random.random()
    if r < 0.85:
        status = 200
    elif r < 0.90:
        status = random.choice([201, 204, 301, 302])
    elif r < 0.94:
        status = 400
    elif r < 0.96:
        status = 401
    elif r < 0.975:
        status = 404
    elif r < 0.985:
        status = 500
    elif r < 0.99:
        status = 403
    else:
        status = random.choice([502, 503])

    # Latency distribution — mostly fast, some slow
    if status >= 500:
        latency_ms = random.randint(1000, 30000)  # errors are slow
    elif "search" in endpoint or "export" in endpoint or "report" in endpoint:
        latency_ms = random.randint(50, 5000)  # search/reports can be slow
    else:
        latency_ms = int(random.lognormvariate(3.5, 1.2))  # log-normal: mostly 10-100ms
        latency_ms = max(1, min(latency_ms, 15000))

    # Build query params
    query_params = {}
    if "search" in endpoint:
        query_params["q"] = random.choice(["laptop", "phone", "headphones", "monitor", "keyboard"])
        query_params["page"] = str(random.randint(1, 50))
        query_params["limit"] = str(random.choice([10, 20, 50, 100]))
    elif "{id}" in endpoint:
        query_params["expand"] = random.choice(["details", "history", "metadata", ""])
    if random.random() < 0.05:
        query_params["filter"] = random.choice(["status:active", "role:admin", "date:2024"])

    # SQL injection attempts from suspicious IPs
    is_sqli = False
    if ip in ["203.0.113.42", "203.0.113.99"] and random.random() < 0.15:
        is_sqli = True
        param_key = random.choice(["q", "id", "filter", "sort"])
        query_params[param_key] = random.choice(SQL_INJECTION_PAYLOADS)

    # Brute force login attempts
    is_brute_force = False
    if ip == "198.51.100.7" and endpoint == "/api/auth/login" and random.random() < 0.8:
        is_brute_force = True
        status = 401

    # Build request headers
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json",
        "X-Request-ID": hashlib.md5(f"{idx}-{random.random()}".encode()).hexdigest(),
        "X-Forwarded-For": ip,
    }
    if random.random() < 0.7:
        headers["Authorization"] = f"Bearer {''.join(random.choices(string.ascii_letters + string.digits, k=40))}"
    if method in ["POST", "PUT", "PATCH"]:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(random.randint(50, 5000))

    # Build response body
    response_body = None
    if status == 200:
        base_endpoint = endpoint.split("{")[0].rstrip("/")
        if base_endpoint in RESPONSE_BODIES:
            response_body = RESPONSE_BODIES[base_endpoint]()
        else:
            response_body = {"status": "ok", "data": {"id": random.randint(1, 9999)}}
    elif status in ERROR_MESSAGES:
        response_body = {
            "error": {
                "code": status,
                "message": random.choice(ERROR_MESSAGES[status]),
                "details": {
                    "request_id": headers["X-Request-ID"],
                    "timestamp": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{ts_hour:02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}Z",
                },
            }
        }
        if status == 500:
            response_body["error"]["details"]["stack_trace"] = generate_stack_trace()

    # Build the log entry
    entry = {
        "timestamp": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{ts_hour:02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}.{random.randint(0,999):03d}Z",
        "request": {
            "method": method,
            "endpoint": endpoint,
            "url": f"https://api.example.com{endpoint.replace('{id}', str(random.randint(1, 9999)))}",
            "query_params": query_params if query_params else None,
            "headers": headers,
            "body_size": random.randint(0, 5000) if method in ["POST", "PUT", "PATCH"] else 0,
        },
        "response": {
            "status_code": status,
            "latency_ms": latency_ms,
            "body_size": random.randint(100, 50000) if response_body else 0,
            "body": response_body,
            "headers": {
                "Content-Type": "application/json",
                "X-RateLimit-Remaining": str(random.randint(0, 1000)),
                "X-RateLimit-Reset": str(random.randint(1700000000, 1710000000)),
                "Cache-Control": random.choice(["no-cache", "max-age=300", "max-age=3600", "private"]),
            },
        },
        "metadata": {
            "server": random.choice(["web-01", "web-02", "web-03", "web-04"]),
            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-northeast-1"]),
            "version": random.choice(["v2.14.3", "v2.14.4", "v2.15.0-beta"]),
            "user_id": username,
            "session_id": hashlib.md5(f"{username}-{random.randint(1,100)}".encode()).hexdigest()[:16],
            "ip_address": ip,
        },
        "flags": {
            "is_authenticated": "Authorization" in headers,
            "is_bot": any(bot in headers["User-Agent"] for bot in ["curl", "python-requests", "Postman"]),
            "is_suspicious": is_sqli or is_brute_force,
            "security_tags": (["sql_injection_attempt"] if is_sqli else []) + (["brute_force"] if is_brute_force else []),
        },
    }

    return entry


def generate_stack_trace():
    traces = [
        """java.lang.NullPointerException
    at com.example.service.OrderService.processPayment(OrderService.java:142)
    at com.example.controller.OrderController.createOrder(OrderController.java:87)
    at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
    at org.springframework.web.servlet.FrameworkServlet.service(FrameworkServlet.java:897)""",
        """java.sql.SQLException: Cannot acquire connection from pool
    at com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:695)
    at com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:197)
    at com.example.repository.UserRepository.findById(UserRepository.java:45)""",
        """redis.clients.jedis.exceptions.JedisConnectionException: Could not get a resource from the pool
    at redis.clients.jedis.util.Pool.getResource(Pool.java:84)
    at com.example.cache.RedisCacheService.get(RedisCacheService.java:52)
    at com.example.service.ProductService.getProduct(ProductService.java:78)""",
        """org.apache.kafka.common.errors.TimeoutException: Topic partition-0 not available
    at org.apache.kafka.clients.producer.KafkaProducer.doSend(KafkaProducer.java:963)
    at com.example.events.EventPublisher.publish(EventPublisher.java:34)
    at com.example.service.NotificationService.sendNotification(NotificationService.java:91)""",
        """Traceback (most recent call last):
  File "/app/services/report_generator.py", line 234, in generate
    data = self.aggregator.compute(query, date_range)
  File "/app/services/data_aggregator.py", line 89, in compute
    result = self.db.execute(query)
psycopg2.OperationalError: server closed the connection unexpectedly""",
    ]
    return random.choice(traces)


def main():
    print("Generating testbench_1M.json (~4MB, ~1M tokens)...")

    entries = []
    for i in range(50000):
        ts_hour = random.randint(0, 23)
        entries.append(generate_entry(i, ts_hour))

        if (i + 1) % 10000 == 0:
            print(f"  {i + 1}/50,000 entries generated...")

    output_path = os.path.join(os.path.dirname(__file__), "testbench_1M.json")
    with open(output_path, "w") as f:
        json.dump(entries, f, indent=2)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    est_tokens = int(size_mb * 250000)  # ~250K tokens per MB for JSON

    print(f"\nGenerated: {output_path}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Records: {len(entries):,}")
    print(f"Estimated tokens: ~{est_tokens:,}")
    print()
    print("Test prompts:")
    print('  1. "Analyze testbench_1M.json — find all 500 errors and group by endpoint"')
    print('  2. "What are the slowest endpoints? Show p50/p95/p99 latencies"')
    print('  3. "Find all SQL injection attempts in the query parameters"')
    print('  4. "Summarize traffic patterns by hour and status code"')
    print('  5. "Find users with suspicious activity (>100 req/min or auth failures)"')


if __name__ == "__main__":
    main()
