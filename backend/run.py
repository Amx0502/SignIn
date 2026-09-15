import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=2206,
        timeout_graceful_shutdown=2,  # 最多等待 2 秒，超时强制关闭
        log_level="info"
    )
