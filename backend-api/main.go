package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// --- 1. DATA MODELS (Structs & Tags) ---
type Podcast struct {
	ID    string `json:"id"`
	Title string `json:"title"`
	URL   string `json:"url"`
}

type NewsArticle struct {
	Headline string `json:"headline"`
	Text     string `json:"text"`
}

// --- 2. IN-MEMORY STATE & MUTEX ---
var (
	catalog = []Podcast{
		{ID: "1", Title: "Il Resto di Bologna", URL: "https://rss.com/bologna"},
		{ID: "2", Title: "Money Vibes", URL: "https://rss.com/money"},
		{ID: "3", Title: "Bar Carlino", URL: "https://rss.com/bar"},
	}
	catalogLock sync.RWMutex // Read/Write Mutex!
)

// --- 3. BACKGROUND WORKER (Goroutines & Tickers) ---
// This runs forever in the background, simulating fetching RSS feeds.
func startRSSFetcher() {
	ticker := time.NewTicker(10 * time.Second) // Tick every 10 seconds
	defer ticker.Stop()

	for {
		<-ticker.C // Wait for the tick (Channel read)
		fmt.Println("[Worker] Fetching latest RSS feeds in the background...")
		// In a real app, you would parse the XML here and update the DB.
	}
}

// --- 4. HANDLERS ---

// Endpoint for Flutter to get the catalog
func catalogHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	catalogLock.RLock() // RLock allows multiple GET requests to read at once safely
	defer catalogLock.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(catalog)
}

// Endpoint to trigger the Python TTS Microservice
func generateNewsAudioHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var article NewsArticle
	if err := json.NewDecoder(r.Body).Decode(&article); err != nil {
		http.Error(w, "Bad JSON", http.StatusBadRequest)
		return
	}

	// Make an HTTP call to your Python FastAPI TTS service
	fmt.Printf("[Go Backend] Asking FastAPI to read: %s\n", article.Headline)

	// Mocking the request to Python:
	pythonReqBody, _ := json.Marshal(article)
	resp, err := http.Post("http://localhost:8000/tts/vits", "application/json", bytes.NewBuffer(pythonReqBody))

	if err != nil || resp.StatusCode != 200 {
		http.Error(w, "TTS Engine failed", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close() // Don't forget to close the response body!

	// Pretend Python gave us a URL back
	responseToFlutter := map[string]string{
		"audio_url": "https://cdn.quotidiano.net/audio/generated_news_123.wav",
	}

	w.WriteHeader(http.StatusCreated)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(responseToFlutter)
}

// --- 5. MAIN ---
func main() {
	// Launch the RSS fetcher in a background Goroutine immediately
	go startRSSFetcher()

	// Register Routes
	http.HandleFunc("/catalog", catalogHandler)
	http.HandleFunc("/generate-audio", generateNewsAudioHandler)

	fmt.Println("🎧 Quotidiano Audio Backend running on :8080...")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		fmt.Printf("Server crashed: %v\n", err)
	}
}
