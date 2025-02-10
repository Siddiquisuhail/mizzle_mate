from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
from log.logging_config import logger
import anyio

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        body = await request.body()

        logger.info({
            "event": "request",
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body.decode("utf-8")
        })

        response = await call_next(request)
        process_time = time.time() - start_time

        send_stream, receive_stream = anyio.create_memory_object_stream(max_buffer_size=1024)
        response_body = []

        async def send_wrapper():
            async for chunk in response.body_iterator:
                await send_stream.send(chunk)
                response_body.append(chunk)
            await send_stream.aclose()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(send_wrapper)

            # Read the response body asynchronously
            new_body = b"".join([chunk async for chunk in receive_stream])

        
        response = Response(content=new_body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)

        logger.info({
            "event": "response",
            "status_code": response.status_code,
            "time_taken": f"{process_time:.3f}s",
            "body": new_body.decode("utf-8", errors="ignore")
        })
        
        return response













# from fastapi import Request
# from starlette.middleware.base import BaseHTTPMiddleware
# import time
# from log.logging_config import logger

# class LoggingMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         start_time = time.time()
#         body = await request.body()

#         logger.info({
#             "event": "request",
#             "method": request.method,
#             "url": str(request.url),
#             "headers": dict(request.headers),
#             "body": body.decode("utf-8")
#         })

#         response = await call_next(request)
#         process_time = time.time() - start_time

#         response_body = [chunk async for chunk in response.body_iterator] if hasattr(response, "body_iterator") else []
#         response.body_iterator = iter(response_body)

#         logger.info({
#             "event": "response",
#             "status_code": response.status_code,
#             "time_taken": f"{process_time:.3f}s",
#             "body": b''.join(response_body).decode("utf-8", errors="ignore")
#         })
#         return response
