// Nemori Engine Test File — Rust
// Tests every engine feature that applies to Rust code.
//
// Features tested:
//   L1a   minify: strip_inline_comments, collapse_blank_lines, strip_indentation
//   L1b   @m substitution: frequency-ordered aliases
//   L1d   @t type aliases: BX, RC, AR, Option, Result, Vec, HashMap, String, Arc, Mutex
//   Item8 @b block dedup: identical function bodies

use std::collections::HashMap;
use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, Instant};
use std::io::{self, Read, Write, BufRead, BufReader, BufWriter};
use std::fmt::{self, Display, Debug};

// =====================================================================
// SECTION 1: @t Type Alias Candidates (Rust)
// =====================================================================

type StringMap = HashMap<String, String>;
type SharedState = Arc<Mutex<HashMap<String, String>>>;
type ResultBox = Result<Box<dyn std::error::Error>, Box<dyn std::error::Error>>;
type ConfigValue = Option<String>;

// =====================================================================
// SECTION 2: @m Substitution Candidates
// =====================================================================

struct ConnectionPoolManager {
    active_connection_list: Vec<String>,
    max_connection_count: usize,
    error_count: u32,
    total_request_count: u32,
}

impl ConnectionPoolManager {
    fn new(max_connection_count: usize) -> Self {
        ConnectionPoolManager {
            active_connection_list: Vec::new(),
            max_connection_count,
            error_count: 0,
            total_request_count: 0,
        }
    }

    fn initialize_connection_pool(&mut self) {
        for i in 0..self.max_connection_count {
            let connection = self.create_connection(i);
            self.active_connection_list.push(connection);
        }
    }

    fn create_connection(&self, id: usize) -> String {
        format!("conn_{}", id)
    }

    fn get_all_active_sessions(&self) -> Vec<String> {
        self.active_connection_list.clone()
    }

    fn shutdown_connection_pool(&mut self) {
        self.active_connection_list.clear();
    }
}

// =====================================================================
// SECTION 3: Block Dedup
// =====================================================================

fn identical_method_one(input: &str) -> String {
    let parsed = parse_connection_string(input);
    let validated = validate_parsed(&parsed);
    create_pool(&validated)
}

fn identical_method_two(input: &str) -> String {
    let parsed = parse_connection_string(input);
    let validated = validate_parsed(&parsed);
    create_pool(&validated)
}

fn identical_method_three(input: &str) -> String {
    let parsed = parse_connection_string(input);
    let validated = validate_parsed(&parsed);
    create_pool(&validated)
}

fn parse_connection_string(s: &str) -> String { s.to_string() }
fn validate_parsed(p: &str) -> String { p.to_string() }
fn create_pool(v: &str) -> String { v.to_string() }

// =====================================================================
// SECTION 4: @sig Method Signature Dedup
// =====================================================================

fn calculate_metric(data_point: f64, window_size: i32) -> i32 {
    (data_point * window_size as f64) as i32
}

fn calculate_average(data_point: f64, window_size: i32) -> i32 {
    if window_size > 0 {
        (data_point / window_size as f64) as i32
    } else {
        0
    }
}

fn calculate_maximum(data_point: f64, window_size: i32) -> i32 {
    let a = data_point as i32;
    if a > window_size { a } else { window_size }
}

// =====================================================================
// SECTION 5: Pattern Dictionary Candidates
// =====================================================================

fn pattern_alpha() -> String {
    let mut manager = ConnectionPoolManager::new(10);
    manager.initialize_connection_pool();
    let sessions = manager.get_all_active_sessions();
    if sessions.is_empty() {
        "empty".to_string()
    } else {
        sessions[0].clone()
    }
}

fn pattern_beta() -> String {
    let mut manager = ConnectionPoolManager::new(5);
    manager.initialize_connection_pool();
    let sessions = manager.get_all_active_sessions();
    if sessions.is_empty() {
        "empty".to_string()
    } else {
        sessions[0].clone()
    }
}

fn pattern_gamma() -> String {
    let mut manager = ConnectionPoolManager::new(8);
    manager.initialize_connection_pool();
    let sessions = manager.get_all_active_sessions();
    if sessions.is_empty() {
        "empty".to_string()
    } else {
        sessions[0].clone()
    }
}

// =====================================================================
// SECTION 6: Minification Test
// =====================================================================

fn minification_test(a: i32, b: i32) -> i32 {
    // This comment should be stripped
    let x = a + b; /* Block comment */
    let y = a - b;
    // Another comment

    let z = x * y;

    z + x + y
}

// =====================================================================
// SECTION 7: String Literal Protection
// =====================================================================

fn string_literal_test() {
    let _x: &str = "active_connection_list should not be aliased";
    let _y: &str = "max_connection_count in quotes";
}

// =====================================================================
// SECTION 8: Large Struct (maximize savings)
// =====================================================================

struct LargeServiceClass {
    connection_pool_manager: Arc<Mutex<ConnectionPoolManager>>,
    max_retry_count: u32,
    timeout_duration: Duration,
    active_connection_list: Vec<String>,
    response_cache: HashMap<String, String>,
    error_count: u32,
    total_request_count: u32,
}

impl LargeServiceClass {
    fn new(
        connection_pool_manager: Arc<Mutex<ConnectionPoolManager>>,
        max_retry_count: u32,
        timeout_seconds: u64,
    ) -> Self {
        LargeServiceClass {
            connection_pool_manager,
            max_retry_count,
            timeout_duration: Duration::from_secs(timeout_seconds),
            active_connection_list: Vec::new(),
            response_cache: HashMap::new(),
            error_count: 0,
            total_request_count: 0,
        }
    }

    fn process_connection_request(&mut self, request_data: &str) -> Option<String> {
        self.total_request_count += 1;
        if self.active_connection_list.is_empty() {
            self.initialize_connection_pool();
        }
        let connection = self.active_connection_list.pop()?;
        let response = self.send_request(&connection, request_data);
        self.response_cache.insert(request_data.to_string(), response.clone());
        self.active_connection_list.push(connection);
        Some(response)
    }

    fn initialize_connection_pool(&mut self) {
        let manager = self.connection_pool_manager.lock().unwrap();
        let sessions = manager.get_all_active_sessions();
        for i in 0..sessions.len() {
            self.active_connection_list.push(format!("conn_{}", i));
        }
    }

    fn send_request(&self, _connection: &str, request_data: &str) -> String {
        format!("response_{}", request_data)
    }

    fn get_statistics(&self) -> HashMap<String, u32> {
        let mut stats = HashMap::new();
        stats.insert("total_requests".to_string(), self.total_request_count);
        stats.insert("errors".to_string(), self.error_count);
        stats.insert("cache_size".to_string(), self.response_cache.len() as u32);
        stats.insert("active_connections".to_string(), self.active_connection_list.len() as u32);
        stats
    }
}

fn main() {
    println!("Nemori Rust test file");
}

// SECTION 9b: Lambda Consolidation Test (duplicate closures for @lam)
fn duplicate_lambda1() {
    let items = vec![1, 2, 3, 4, 5];
    let mapped1: Vec<i32> = items.iter().map(|x| x * 2).collect();
    let filtered: Vec<i32> = items.iter().filter(|x| *x > 2).collect();
    return mapped1.iter().filter(|x| *x > 5).collect::<Vec<i32>>();
}

fn duplicate_lambda2() {
    let items = vec![10, 20, 30, 40, 50];
    let mapped1: Vec<i32> = items.iter().map(|x| x * 2).collect();
    let filtered: Vec<i32> = items.iter().filter(|x| *x > 2).collect();
    return mapped1.iter().filter(|x| *x > 5).collect::<Vec<i32>>();
}

fn duplicate_lambda3() {
    let items = vec![100, 200, 300, 400, 500];
    let mapped1: Vec<i32> = items.iter().map(|x| x * 2).collect();
    let filtered: Vec<i32> = items.iter().filter(|x| *x > 2).collect();
    return mapped1.iter().filter(|x| *x > 5).collect::<Vec<i32>>();
}
