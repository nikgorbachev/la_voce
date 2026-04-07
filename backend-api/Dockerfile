FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod ./
# If you have a go.sum, uncomment the next line:
# COPY go.sum ./
RUN go mod download

COPY . .
RUN go build -o backend-binary main.go

# Step 2: Use a minimal image to run the binary
FROM alpine:latest
WORKDIR /root/
COPY --from=builder /app/backend-binary .

EXPOSE 8080
CMD ["./backend-binary"]