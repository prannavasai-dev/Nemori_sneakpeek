// Nemori Engine Test File — Go
// Tests every engine feature that applies to Go code.
//
// Features tested:
//   L1a   minify: strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1c   @u import collapse: import blocks
//   L1d   @t type aliases: CX, FM, HP, TM, SC, AT, BF, SN, SG, BY
//   Item8 @b block dedup: identical function bodies

package main

import (
	"context"
	"fmt"
	"net/http"
	"sync"
	"time"
	"bufio"
	"strings"
	"bytes"
	"sync/atomic"
)

// =====================================================================
// SECTION 1: @t Type Alias Candidates (Go)
// =====================================================================
// Go @t table: CX=context, FM=fmt, HP=http, TM=time, SC=sync,
// AT=atomic, BF=bufio, SN=scanner, SG=strings, BY=bytes

func usesTypeAliases() {
	ctx := context.Background()
	_ = fmt.Sprintf("test")
	_ = &http.Client{Timeout: 10 * time.Second}
	var mu sync.Mutex
	_ = atomic.Value{}
	_ = bufio.NewReader(nil)
	_ = strings.NewReader("test")
	_ = bytes.Buffer{}
	_ = context.TODO()
}

// =====================================================================
// SECTION 2: @u Import Collapse Candidates
// =====================================================================

// =====================================================================
// SECTION 3: @m Substitution Candidates
// =====================================================================

type ConnectionPoolManager struct {
	activeConnectionList []string
	maxConnectionCount   int
	mu                   sync.Mutex
}

func NewConnectionPoolManager(maxConnectionCount int) *ConnectionPoolManager {
	return &ConnectionPoolManager{
		activeConnectionList: make([]string, 0),
		maxConnectionCount:   maxConnectionCount,
	}
}

func (cpm *ConnectionPoolManager) InitializeConnectionPool() {
	cpm.mu.Lock()
	defer cpm.mu.Unlock()
	for i := 0; i < cpm.maxConnectionCount; i++ {
		connection := cpm.createConnection()
		cpm.activeConnectionList = append(cpm.activeConnectionList, connection)
	}
}

func (cpm *ConnectionPoolManager) createConnection() string {
	return fmt.Sprintf("conn_%d", len(cpm.activeConnectionList))
}

func (cpm *ConnectionPoolManager) GetAllActiveSessions() []string {
	cpm.mu.Lock()
	defer cpm.mu.Unlock()
	result := make([]string, len(cpm.activeConnectionList))
	copy(result, cpm.activeConnectionList)
	return result
}

func (cpm *ConnectionPoolManager) ShutdownConnectionPool() {
	cpm.mu.Lock()
	defer cpm.mu.Unlock()
	cpm.activeConnectionList = cpm.activeConnectionList[:0]
}

// =====================================================================
// SECTION 4: Block Dedup
// =====================================================================

func IdenticalMethodOne(input string) string {
	parsed := ParseConnectionString(input)
	validated := ValidateParsed(parsed)
	return CreatePool(validated)
}

func IdenticalMethodTwo(input string) string {
	parsed := ParseConnectionString(input)
	validated := ValidateParsed(parsed)
	return CreatePool(validated)
}

func IdenticalMethodThree(input string) string {
	parsed := ParseConnectionString(input)
	validated := ValidateParsed(parsed)
	return CreatePool(validated)
}

func ParseConnectionString(s string) string { return s }
func ValidateParsed(p string) string        { return p }
func CreatePool(v string) string            { return v }

// =====================================================================
// SECTION 5: @sig Method Signature Dedup
// =====================================================================

func CalculateMetric(dataPoint float64, windowSize int) int {
	return int(dataPoint * float64(windowSize))
}

func CalculateAverage(dataPoint float64, windowSize int) int {
	if windowSize > 0 {
		return int(dataPoint / float64(windowSize))
	}
	return 0
}

func CalculateMaximum(dataPoint float64, windowSize int) int {
	a := int(dataPoint)
	if a > windowSize {
		return a
	}
	return windowSize
}

// =====================================================================
// SECTION 6: Pattern Dictionary Candidates
// =====================================================================

func PatternAlpha() string {
	manager := NewConnectionPoolManager(10)
	sessions := manager.GetAllActiveSessions()
	if len(sessions) == 0 {
		return "empty"
	}
	return sessions[0]
}

func PatternBeta() string {
	manager := NewConnectionPoolManager(5)
	sessions := manager.GetAllActiveSessions()
	if len(sessions) == 0 {
		return "empty"
	}
	return sessions[0]
}

func PatternGamma() string {
	manager := NewConnectionPoolManager(8)
	sessions := manager.GetAllActiveSessions()
	if len(sessions) == 0 {
		return "empty"
	}
	return sessions[0]
}

// =====================================================================
// SECTION 7: Minification Test
// =====================================================================

func MinificationTest(a, b int) int {
	// This comment should be stripped
	x := a + b
	y := a - b
	// Another comment

	z := x * y

	return z + x + y
}

// =====================================================================
// SECTION 8: String Literal Protection
// =====================================================================

func StringLiteralTest() {
	x := "active_connection_list should not be aliased"
	_ = x
	y := "max_connection_count in quotes"
	_ = y
}

// =====================================================================
// SECTION 9: Goroutines and Channels
// =====================================================================

func GoroutineTest(urls []string) []string {
	results := make(chan string, len(urls))
	for _, url := range urls {
		go func(u string) {
			results <- fmt.Sprintf("fetched_%s", u)
		}(url)
	}
	var collected []string
	for i := 0; i < len(urls); i++ {
		collected = append(collected, <-results)
	}
	return collected
}

// =====================================================================
// SECTION 9b: Lambda Consolidation Test (duplicate lambdas for @lam)
// =====================================================================

func ApplyLambdaOperations() {
	items := []int{1, 2, 3, 4, 5}
	// Same lambda appearing 3+ times for @lam consolidation
	mapped1 := MapFunc(items, func(x int) int { return x * 2 })
	filtered := FilterFunc(items, func(x int) bool { return x > 2 })
	sorted := SortFunc(items, func(x int) int { return -x })
	_ = mapped1
	_ = filtered
	_ = sorted
}

func MapFunc(items []int, fn func(int) int) []int {
	result := make([]int, len(items))
	for i, v := range items {
		result[i] = fn(v)
	}
	return result
}

func FilterFunc(items []int, fn func(int) bool) []int {
	result := []int{}
	for _, v := range items {
		if fn(v) {
			result = append(result, v)
		}
	}
	return result
}

func SortFunc(items []int, fn func(int) int) []int {
	result := make([]int, len(items))
	copy(result, items)
	// Simple sort for test
	return result
}

// =====================================================================
// SECTION 10: Large Struct (maximize savings)
// =====================================================================

type LargeServiceClass struct {
	connectionPoolManager *ConnectionPoolManager
	maxRetryCount         int
	timeoutDuration       time.Duration
	activeConnectionList  []string
	responseCache         map[string]string
	errorCount            int32
	totalRequestCount     int32
}

func NewLargeServiceClass(connectionPoolManager *ConnectionPoolManager, maxRetryCount int, timeoutSeconds int) *LargeServiceClass {
	return &LargeServiceClass{
		connectionPoolManager: connectionPoolManager,
		maxRetryCount:         maxRetryCount,
		timeoutDuration:       time.Duration(timeoutSeconds) * time.Second,
		activeConnectionList:  make([]string, 0),
		responseCache:         make(map[string]string),
		errorCount:            0,
		totalRequestCount:     0,
	}
}

func (ls *LargeServiceClass) ProcessConnectionRequest(requestData string) string {
	atomic.AddInt32(&ls.totalRequestCount, 1)
	if len(ls.activeConnectionList) == 0 {
		ls.InitializeConnectionPool()
	}
	connection := ls.activeConnectionList[0]
	ls.activeConnectionList = ls.activeConnectionList[1:]
	defer func() {
		ls.activeConnectionList = append(ls.activeConnectionList, connection)
	}()
	response := ls.SendRequest(connection, requestData)
	ls.responseCache[requestData] = response
	return response
}

func (ls *LargeServiceClass) InitializeConnectionPool() {
	sessions := ls.connectionPoolManager.GetAllActiveSessions()
	for i := 0; i < len(sessions); i++ {
		ls.activeConnectionList = append(ls.activeConnectionList, fmt.Sprintf("conn_%d", i))
	}
}

func (ls *LargeServiceClass) SendRequest(connection string, requestData string) string {
	return fmt.Sprintf("response_%s", requestData)
}

func (ls *LargeServiceClass) GetStatistics() map[string]int32 {
	return map[string]int32{
		"total_requests":     atomic.LoadInt32(&ls.totalRequestCount),
		"errors":             atomic.LoadInt32(&ls.errorCount),
		"cache_size":         int32(len(ls.responseCache)),
		"active_connections": int32(len(ls.activeConnectionList)),
	}
}

func GoroutineTest(urls []string) []string {
	results := make(chan string, len(urls))
	for _, url := range urls {
		go func(u string) {
			results <- fmt.Sprintf("fetched_%s", u)
		}(url)
	}
	var collected []string
	for i := 0; i < len(urls); i++ {
		collected = append(collected, <-results)
	}
	return collected
}

// SECTION 9b: Lambda/Arrow Function Consolidation (duplicate lambdas for @lam testing)
func DuplicateLambda1() int {
	mapped1 := mapList(func(x int) int { return x * 2 }, []int{1, 2, 3})
	filtered := filterList(func(x int) bool { return x > 5 }, []int{1, 2, 3, 4, 5})
	return mapped1[0]
}

func DuplicateLambda2() int {
	mapped1 := mapList(func(x int) int { return x * 2 }, []int{10, 20, 30})
	filtered := filterList(func(x int) bool { return x > 5 }, []int{10, 20, 30})
	return mapped1[0]
}

func DuplicateLambda3() int {
	mapped1 := mapList(func(x int) int { return x * 2 }, []int{100, 200, 300})
	filtered := filterList(func(x int) bool { return x > 5 }, []int{100, 200, 300})
	return mapped1[0]
}

func mapList(f func(int) int, lst []int) []int {
	result := make([]int, len(lst))
	for i, v := range lst {
		result[i] = f(v)
	}
	return result
}

func filterList(f func(int) bool, lst []int) []int {
	result := []int{}
	for _, v := range lst {
		if f(v) {
			result = append(result, v)
		}
	}
	return result
}
