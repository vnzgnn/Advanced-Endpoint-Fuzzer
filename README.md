# Advanced Endpoint Fuzzer

![Testo alternativo](https://github.com/vnzgnn/Advanced-Endpoint-Fuzzer/blob/main/advanced_endpoint_fuzzer_logo.jpg)

Advanced Endpoint Fuzzer is an asynchronous tool designed to discover and test API endpoints. It offers high performance, customizable options, and detailed reporting.

## Features

- Asynchronous requests for high-speed fuzzing
- Custom wordlist support
- Rate limiting
- Concurrent request handling
- Detailed output with status code analysis
- JSON output for further processing
- SSL certificate validation bypass option

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/vnzgnn/advanced-endpoint-fuzzer.git
   ```

2. Navigate to the project directory:
   ```
   cd advanced-endpoint-fuzzer
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

To start fuzzing with default options:

```
python advanced_endpoint_fuzzer.py https://api.example.com
```

### Advanced Usage

For more control over the fuzzing process:

```
python advanced_endpoint_fuzzer.py https://api.example.com --wordlist custom_wordlist.txt --rate-limit 10 --concurrency 5 --output results.json --verbose
```

### Options

- `--wordlist`: Path to a custom wordlist file
- `--rate-limit`: Number of requests per second
- `--concurrency`: Number of concurrent requests
- `--output`: File to save the results in JSON format
- `--verbose`: Enable verbose output
- `--ignore-ssl`: Ignore SSL certificate validation

For a complete list of options:

```
python advanced_endpoint_fuzzer.py --help
```

## Output

The fuzzer provides real-time output during the fuzzing process and a summary at the end. If specified, a detailed JSON report is saved to the output file.

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for educational and testing purposes only. Always ensure you have permission before testing on any systems you do not own or have explicit permission to test.
