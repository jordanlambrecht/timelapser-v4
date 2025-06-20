#!/bin/bash

# ==============================================================================
# Timelapser V4 - Comprehensive Full-Stack Architecture Generation Script
# ==============================================================================
# This script generates a comprehensive set of architecture diagrams and code
# analysis reports for the entire Timelapser V4 application stack, optimized
# for AI consumption and development insights.
#
# 🔧 BACKEND ANALYSIS TOOLS:
# - openapi: FastAPI OpenAPI specification with markdown tables
# - code2flow: Function call graphs (SVG/PNG)
# - pydeps: Module dependency graphs (SVG/PNG)
# - vulture: Dead code detection
# - radon: Code complexity analysis
# - prospector: Comprehensive code analysis
# - pdoc: Documentation from docstrings (markdown)
# - alembic: Database migration analysis
#
# 🎨 FRONTEND ANALYSIS TOOLS:
# - typescript: TypeScript compilation and type checking
# - eslint: JavaScript/TypeScript linting analysis (COMMENTED OUT)
# - nextjs: Next.js project structure and optimization analysis
# - tailwind: Tailwind CSS usage and optimization analysis
# - packagejson: Frontend dependency analysis
#
# 🗄️ DATABASE & INFRASTRUCTURE:
# - tbls: Database schema diagrams (SVG/PNG)
# - env-analysis: Environment configuration analysis
# - docker: Docker configuration analysis (if present) (COMMENTED OUT)
#
# 🔗 FULL-STACK INTEGRATION:
# - api-contracts: API contract validation between frontend/backend
# - type-sync: Pydantic-TypeScript type synchronization verification
#
# Usage:
#   ./generate_architecture.sh                           - Generate full report
#   ./generate_architecture.sh clean                     - Remove all reports
#   ./generate_architecture.sh --reports typescript eslint - Run only specified tools
#   ./generate_architecture.sh --exclude tbls radon      - Run all except specified
#
# All output is saved to _architecture/report_TIMESTAMP/ with tool-specific folders.
# ==============================================================================

# === CONFIGURATION VARIABLES ===
# Modify these settings to customize tool behavior without editing the script logic

# General settings
CONFIDENCE_LEVEL=80      # Vulture confidence threshold (0-100)
COMPLEXITY_THRESHOLD='C' # Radon complexity threshold (A=best, F=worst)
DB_TIMEOUT=30            # Database connection timeout for tbls (seconds)
# ESLINT_MAX_WARNINGS=50   # Maximum ESLint warnings to display (COMMENTED OUT)
# TYPESCRIPT_STRICT=true   # Use strict TypeScript checking (COMMENTED OUT)

# Output format preferences
GENERATE_SVG=true  # Generate SVG files for graphs
GENERATE_PNG=true  # Generate PNG files for graphs
GENERATE_DOT=false # Generate DOT files (disabled for AI focus)

# Directory ignore patterns (applied to all scanning tools)
IGNORE_PATTERNS="**/venv/** **/__pycache__/** **/*.pyc **/.git/** **/node_modules/**"

# Tool-specific options (modify flags and parameters here)
CODE2FLOW_OPTS="--language py --quiet"
PYDEPS_OPTS="--noshow --cluster --max-bacon 3 --exclude venv --exclude site-packages --exclude __pycache__ --exclude .venv --exclude env --exclude backend/venv --exclude backend/.venv --exclude backend/env --exclude '*/venv/*' --exclude '*/site-packages/*' --exclude ./backend/venv --log ERROR"
VULTURE_OPTS=""
RADON_OPTS="-s -a"
PROSPECTOR_OPTS=""
PDOC_OPTS="-d markdown"
TBLS_OPTS=""
# TYPESCRIPT_OPTS="--noEmit --strict" # (COMMENTED OUT)
# ESLINT_OPTS="--format json --max-warnings 50" # (COMMENTED OUT)
# TAILWIND_OPTS="" # (COMMENTED OUT)
# ALEMBIC_OPTS="" # (COMMENTED OUT)

# Project structure
TIMESTAMP=$(date "+%Y%m%d_%H%M%S")
BASE_OUTPUT_DIR="_architecture"
OUTPUT_DIR="$BASE_OUTPUT_DIR/report_$TIMESTAMP"
BACKEND_ROOT="backend"
BACKEND_COMPONENTS_PATHS="$BACKEND_ROOT/app $BACKEND_ROOT/worker.py $BACKEND_ROOT/rtsp_capture.py $BACKEND_ROOT/video_generator.py"
# FRONTEND_ROOT="src" # (COMMENTED OUT)
# FRONTEND_COMPONENTS_PATHS="$FRONTEND_ROOT/app $FRONTEND_ROOT/components $FRONTEND_ROOT/hooks $FRONTEND_ROOT/lib" # (COMMENTED OUT)
# PACKAGE_JSON="package.json" # (COMMENTED OUT)
# TSCONFIG_JSON="tsconfig.json" # (COMMENTED OUT)
# TAILWIND_CONFIG="tailwind.config.ts" # (COMMENTED OUT)
# NEXT_CONFIG="next.config.js" # (COMMENTED OUT)

# Available tools (used for argument parsing)
ALL_TOOLS=("openapi" "code2flow" "pydeps" "vulture" "radon" "prospector" "pdoc" "filetree" "alembic" "typescript" "nextjs" "tailwind" "packagejson" "tbls" "env-analysis" "api-contracts" "type-sync")
# Commented out: "eslint" "docker"
SELECTED_TOOLS=()
RESULTS=()

# === HELPER FUNCTIONS ===

# Function to check if a tool is available
check_tool_available() {
  local tool=$1
  local required_cmds=""

  case $tool in
  "openapi") required_cmds="python" ;;
  "code2flow") required_cmds="code2flow dot" ;;
  "pydeps") required_cmds="pydeps" ;;
  "vulture") required_cmds="vulture" ;;
  "radon") required_cmds="radon" ;;
  "prospector") required_cmds="prospector" ;;
  "pdoc") required_cmds="pdoc" ;;
  "filetree") required_cmds="tree" ;;
  "alembic") required_cmds="alembic python" ;;
  "typescript") required_cmds="tsc" ;;
  # "eslint") required_cmds="eslint" ;;  # COMMENTED OUT
  "nextjs") required_cmds="node npm" ;;
  "tailwind") required_cmds="node" ;;
  "packagejson") required_cmds="node npm" ;;
  "tbls") required_cmds="tbls dot" ;;
  "env-analysis") required_cmds="python" ;;
  # "docker") required_cmds="docker" ;;  # COMMENTED OUT
  "api-contracts") required_cmds="python node" ;;
  "type-sync") required_cmds="python node" ;;
  esac

  for cmd in $required_cmds; do
    if ! command -v $cmd &>/dev/null; then
      echo "❌ Missing required command '$cmd' for tool '$tool'"
      return 1
    fi
  done
  return 0
}

# Function to run a command with error handling and result tracking
run_with_error_handling() {
  local tool_name=$1
  local description=$2
  local command=$3
  local expected_outputs=$4

  echo "  -> $description"

  # Create tool-specific directory
  mkdir -p "$OUTPUT_DIR/$tool_name"

  # Run command and capture output
  local temp_log=$(mktemp)
  eval "$command" 2>&1 | tee "$temp_log"
  local exit_code=${PIPESTATUS[0]}

  # Parse output for errors and warnings
  local errors=$(grep -i "error\|failed\|exception" "$temp_log" | head -5 || true)
  local warnings=$(grep -i "warning\|deprecated" "$temp_log" | head -5 || true)

  # Check if expected outputs were created
  local created_files=()
  if [ ! -z "$expected_outputs" ]; then
    IFS=',' read -ra OUTPUTS <<<"$expected_outputs"
    for output in "${OUTPUTS[@]}"; do
      if [ -f "$output" ]; then
        created_files+=("$output")
      fi
    done
  fi

  # Record result
  local success="false"
  if [ $exit_code -eq 0 ] && ([ -z "$expected_outputs" ] || [ ${#created_files[@]} -gt 0 ]); then
    success="true"
    echo "     ✅ $tool_name completed successfully"
  else
    echo "     ⚠️  $tool_name completed with issues (exit code: $exit_code)"
  fi

  # Store result in global array
  RESULTS+=("$tool_name|$success|${created_files[*]}|$errors|$warnings")

  rm "$temp_log"
}

# Function to convert OpenAPI JSON to markdown tables
generate_openapi_markdown() {
  local json_file=$1
  local md_file=$2

  cat >generate_openapi_md.py <<'EOF'
import json
import sys
from pathlib import Path

def generate_openapi_markdown(json_file, md_file):
    try:
        with open(json_file, 'r') as f:
            spec = json.load(f)
        
        with open(md_file, 'w') as f:
            f.write("# FastAPI OpenAPI Specification\n\n")
            
            # Basic info
            info = spec.get('info', {})
            f.write(f"**Title:** {info.get('title', 'N/A')}  \n")
            f.write(f"**Version:** {info.get('version', 'N/A')}  \n")
            f.write(f"**Description:** {info.get('description', 'N/A')}  \n\n")
            
            # Endpoints table
            f.write("## API Endpoints\n\n")
            f.write("| Method | Path | Summary | Tags |\n")
            f.write("|--------|------|---------|------|\n")
            
            paths = spec.get('paths', {})
            for path, methods in paths.items():
                for method, details in methods.items():
                    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                        summary = details.get('summary', 'N/A')
                        tags = ', '.join(details.get('tags', []))
                        f.write(f"| {method.upper()} | {path} | {summary} | {tags} |\n")
            
            # Models/Schemas
            components = spec.get('components', {})
            schemas = components.get('schemas', {})
            
            if schemas:
                f.write("\n## Data Models\n\n")
                for schema_name, schema_def in schemas.items():
                    f.write(f"### {schema_name}\n\n")
                    
                    schema_type = schema_def.get('type', 'object')
                    f.write(f"**Type:** {schema_type}  \n")
                    
                    if 'description' in schema_def:
                        f.write(f"**Description:** {schema_def['description']}  \n")
                    
                    properties = schema_def.get('properties', {})
                    if properties:
                        f.write("\n**Properties:**\n\n")
                        f.write("| Field | Type | Required | Description |\n")
                        f.write("|-------|------|----------|-------------|\n")
                        
                        required_fields = set(schema_def.get('required', []))
                        for prop_name, prop_def in properties.items():
                            prop_type = prop_def.get('type', 'unknown')
                            if 'format' in prop_def:
                                prop_type += f" ({prop_def['format']})"
                            is_required = "Yes" if prop_name in required_fields else "No"
                            description = prop_def.get('description', 'N/A')
                            f.write(f"| {prop_name} | {prop_type} | {is_required} | {description} |\n")
                    
                    f.write("\n")
        
        return True
    except Exception as e:
        print(f"Error generating OpenAPI markdown: {e}")
        return False

if __name__ == "__main__":
    success = generate_openapi_markdown(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)
EOF

  timeout 30 python generate_openapi_md.py "$json_file" "$md_file"
  local result=$?
  rm -f generate_openapi_md.py
  return $result
}

# Function to generate final report summary
generate_report_summary() {
  local summary_file="$OUTPUT_DIR/REPORT_SUMMARY.md"

  cat >"$summary_file" <<EOF
# Architecture Generation Report

**Generated:** $(date)  
**Project:** Timelapser V4  
**Report Directory:** $OUTPUT_DIR  

## Tool Execution Summary

EOF

  # Parse results and create checkboxes
  local total_tools=0
  local successful_tools=0

  for result in "${RESULTS[@]}"; do
    IFS='|' read -r tool success files errors warnings <<<"$result"
    total_tools=$((total_tools + 1))

    if [ "$success" = "true" ]; then
      echo "- [x] **$tool** - ✅ Completed successfully" >>"$summary_file"
      successful_tools=$((successful_tools + 1))
    else
      echo "- [ ] **$tool** - ⚠️ Completed with issues" >>"$summary_file"
    fi

    # Add generated files
    if [ ! -z "$files" ] && [ "$files" != " " ]; then
      echo "  - Generated files: \`${files// /, }\`" >>"$summary_file"
    fi
  done

  cat >>"$summary_file" <<EOF

## Overall Status

**Success Rate:** $successful_tools/$total_tools tools completed successfully

## Generated Content Structure

\`\`\`
$OUTPUT_DIR/
├── openapi/          # FastAPI specification & markdown tables
├── code2flow/        # Function call flow diagrams  
├── pydeps/           # Module dependency graphs
├── vulture/          # Dead code analysis
├── radon/            # Code complexity reports
├── prospector/       # Comprehensive code analysis
├── pdoc/             # API documentation from docstrings
├── filetree/         # Project file structure tree
├── alembic/          # Database migration analysis
├── typescript/       # TypeScript type checking results
├── eslint/           # Frontend linting analysis
├── nextjs/           # Next.js project analysis
├── tailwind/         # Tailwind CSS usage analysis
├── packagejson/      # Frontend dependency analysis
├── tbls/             # Database schema diagrams
├── env-analysis/     # Environment configuration analysis
├── docker/           # Docker configuration analysis
├── api-contracts/    # Frontend-backend API contract validation
├── type-sync/        # Pydantic-TypeScript type synchronization
└── REPORT_SUMMARY.md # This summary file
\`\`\`

EOF

  # Add errors and warnings section
  local has_issues=false
  for result in "${RESULTS[@]}"; do
    IFS='|' read -r tool success files errors warnings <<<"$result"
    if [ ! -z "$errors" ] || [ ! -z "$warnings" ]; then
      if [ "$has_issues" = false ]; then
        echo "## Issues and Warnings" >>"$summary_file"
        echo "" >>"$summary_file"
        has_issues=true
      fi

      echo "### $tool" >>"$summary_file"
      if [ ! -z "$errors" ] && [ "$errors" != " " ]; then
        echo "**Errors:**" >>"$summary_file"
        echo "\`\`\`" >>"$summary_file"
        echo "$errors" >>"$summary_file"
        echo "\`\`\`" >>"$summary_file"
      fi
      if [ ! -z "$warnings" ] && [ "$warnings" != " " ]; then
        echo "**Warnings:**" >>"$summary_file"
        echo "\`\`\`" >>"$summary_file"
        echo "$warnings" >>"$summary_file"
        echo "\`\`\`" >>"$summary_file"
      fi
      echo "" >>"$summary_file"
    fi
  done

  if [ "$has_issues" = false ]; then
    echo "## Issues and Warnings" >>"$summary_file"
    echo "" >>"$summary_file"
    echo "No significant issues or warnings detected. ✅" >>"$summary_file"
  fi

  echo "📄 Generated report summary: $summary_file"
}

# === ARGUMENT PARSING ===

# Handle clean command
if [ "$1" = "clean" ]; then
  echo "🧹 Cleaning all architecture reports..."
  if [ -d "_architecture" ]; then
    rm -rf "_architecture"/report_*
    echo "     ✅ Removed all report directories from _architecture"
  else
    echo "     ✅ No _architecture directory found - already clean"
  fi
  echo "🎉 Clean complete!"
  exit 0
fi

# Parse command line arguments for selective tool execution
while [[ $# -gt 0 ]]; do
  case $1 in
  --reports)
    shift
    while [[ $# -gt 0 ]] && [[ $1 != --* ]]; do
      if [[ " ${ALL_TOOLS[*]} " =~ " $1 " ]]; then
        SELECTED_TOOLS+=("$1")
      else
        echo "❌ Unknown tool: $1"
        echo "Available tools: ${ALL_TOOLS[*]}"
        exit 1
      fi
      shift
    done
    ;;
  --exclude)
    shift
    excluded_tools=()
    while [[ $# -gt 0 ]] && [[ $1 != --* ]]; do
      if [[ " ${ALL_TOOLS[*]} " =~ " $1 " ]]; then
        excluded_tools+=("$1")
      else
        echo "❌ Unknown tool: $1"
        echo "Available tools: ${ALL_TOOLS[*]}"
        exit 1
      fi
      shift
    done
    # Add all tools except excluded ones
    for tool in "${ALL_TOOLS[@]}"; do
      if [[ ! " ${excluded_tools[*]} " =~ " $tool " ]]; then
        SELECTED_TOOLS+=("$tool")
      fi
    done
    ;;
  *)
    echo "❌ Unknown argument: $1"
    echo "Usage: $0 [clean|--reports tool1 tool2|--exclude tool1 tool2]"
    echo "Available tools: ${ALL_TOOLS[*]}"
    exit 1
    ;;
  esac
done

# If no tools specified, use all tools
if [ ${#SELECTED_TOOLS[@]} -eq 0 ]; then
  SELECTED_TOOLS=("${ALL_TOOLS[@]}")
fi

# === MAIN EXECUTION ===

echo "🚀 Starting Timelapser V4 comprehensive full-stack architecture analysis..."
echo "📅 Report timestamp: $TIMESTAMP"
echo "📁 Output directory: $OUTPUT_DIR"
echo "🔧 Selected tools: ${SELECTED_TOOLS[*]}"

# Create base directories
mkdir -p "$OUTPUT_DIR"

# Ensure we run from the project root
if [ ! -d "$BACKEND_ROOT" ]; then
  echo "❌ Error: Could not find backend directory. Please run this script from the project root."
  exit 1
fi

# Check prerequisites for selected tools
echo -e "\n🔍 Checking prerequisites for selected tools..."
failed_checks=()
for tool in "${SELECTED_TOOLS[@]}"; do
  if ! check_tool_available "$tool"; then
    failed_checks+=("$tool")
  fi
done

if [ ${#failed_checks[@]} -gt 0 ]; then
  echo "❌ Prerequisites failed for tools: ${failed_checks[*]}"
  echo "Please install missing dependencies and try again."
  exit 1
fi
echo "✅ All prerequisites satisfied."

# === TOOL EXECUTION ===

tool_count=0
total_selected=${#SELECTED_TOOLS[@]}

for tool in "${SELECTED_TOOLS[@]}"; do
  tool_count=$((tool_count + 1))
  echo -e "\n[$tool_count/$total_selected] 🔧 Running $tool..."

  case $tool in
  "openapi")
    # Generate OpenAPI specification and convert to markdown
    mkdir -p "$OUTPUT_DIR/openapi"

    # Create temporary script for OpenAPI generation
    cat >generate_openapi_temp.py <<'EOF'
import json
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add backend to path to allow for app import
sys.path.insert(0, './backend')

try:
    from app.main import app
    with open(sys.argv[1], 'w') as f:
        json.dump(app.openapi(), f, indent=2)
    print("OpenAPI JSON generated successfully")
except Exception as e:
    print(f"Error generating OpenAPI: {e}")
    sys.exit(1)
EOF

    json_file="$OUTPUT_DIR/openapi/fastapi_openapi_spec_$TIMESTAMP.json"
    md_file="$OUTPUT_DIR/openapi/fastapi_api_documentation_$TIMESTAMP.md"

    # Set dummy DATABASE_URL if not present
    export DATABASE_URL=${DATABASE_URL:-"postgresql://user:pass@localhost/db_for_spec_generation"}

    run_with_error_handling "openapi" "Generating FastAPI OpenAPI specification" \
      "python generate_openapi_temp.py '$json_file'" "$json_file"

    # Convert JSON to markdown if JSON was successfully created
    if [ -f "$json_file" ]; then
      if generate_openapi_markdown "$json_file" "$md_file"; then
        echo "     ✅ Generated markdown documentation: $md_file"
      else
        echo "     ⚠️  Failed to generate markdown documentation"
      fi
    fi

    unset DATABASE_URL
    rm -f generate_openapi_temp.py
    ;;

  "code2flow")
    mkdir -p "$OUTPUT_DIR/code2flow"
    base_name="$OUTPUT_DIR/code2flow/backend_function_flow_$TIMESTAMP"

    run_with_error_handling "code2flow" "Generating function call flow diagrams" \
      "code2flow $BACKEND_COMPONENTS_PATHS $CODE2FLOW_OPTS --output '${base_name}.gv'" \
      "${base_name}.gv"

    # Generate image formats if DOT file was created
    if [ -f "${base_name}.gv" ]; then
      if [ "$GENERATE_SVG" = true ]; then
        dot -Tsvg "${base_name}.gv" -o "${base_name}.svg" 2>/dev/null
      fi
      if [ "$GENERATE_PNG" = true ]; then
        dot -Tpng "${base_name}.gv" -o "${base_name}.png" 2>/dev/null
      fi
      # Remove DOT file if not requested
      if [ "$GENERATE_DOT" = false ]; then
        rm "${base_name}.gv"
      fi
    fi
    ;;

  "pydeps")
    mkdir -p "$OUTPUT_DIR/pydeps"

    # Create temporary __init__.py to make backend a package
    touch "$BACKEND_ROOT/__init__.py"

    # Full backend dependencies
    base_name="$OUTPUT_DIR/pydeps/backend_dependencies_$TIMESTAMP"
    run_with_error_handling "pydeps" "Generating module dependency graphs (full backend)" \
      "pydeps $BACKEND_ROOT $PYDEPS_OPTS -T pdf -o '${base_name}.pdf'" \
      "${base_name}.pdf"

    # App-only dependencies
    app_base_name="$OUTPUT_DIR/pydeps/app_dependencies_$TIMESTAMP"
    run_with_error_handling "pydeps" "Generating app-specific dependency graph" \
      "pydeps $BACKEND_ROOT/app $PYDEPS_OPTS -T pdf -o '${app_base_name}.pdf'" \
      "${app_base_name}.pdf"

    # External dependencies list
    ext_deps_file="$OUTPUT_DIR/pydeps/external_dependencies_$TIMESTAMP.md"
    echo "# External Dependencies" >"$ext_deps_file"
    echo "" >>"$ext_deps_file"
    echo "## Python Package Dependencies" >>"$ext_deps_file"
    echo "" >>"$ext_deps_file"

    # Get external dependencies and clean up the output
    pydeps $BACKEND_ROOT --externals --exclude venv --exclude site-packages --exclude __pycache__ --exclude .venv --exclude env --exclude backend/venv --exclude backend/.venv --exclude backend/env --exclude '*/venv/*' --exclude '*/site-packages/*' 2>/dev/null |
      sed 's/\[//g; s/\]//g; s/"//g; s/,//g' |
      grep -v '^$' |
      sort -u |
      while read dep; do
        if [ ! -z "$dep" ] && [ "$dep" != "[" ] && [ "$dep" != "]" ]; then
          echo "- $dep" >>"$ext_deps_file"
        fi
      done

    rm -f "$BACKEND_ROOT/__init__.py"
    ;;

  "vulture")
    mkdir -p "$OUTPUT_DIR/vulture"
    output_file="$OUTPUT_DIR/vulture/dead_code_analysis_$TIMESTAMP.md"

    echo "# Dead Code Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Vulture  " >>"$output_file"
    echo "**Confidence Threshold:** $CONFIDENCE_LEVEL%  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"
    echo "## Potentially Unused Code" >>"$output_file"
    echo "" >>"$output_file"

    run_with_error_handling "vulture" "Scanning for dead code (confidence >= $CONFIDENCE_LEVEL%)" \
      "vulture $BACKEND_COMPONENTS_PATHS $VULTURE_OPTS --min-confidence $CONFIDENCE_LEVEL >> '$output_file'" \
      "$output_file"
    ;;

  "radon")
    mkdir -p "$OUTPUT_DIR/radon"
    output_file="$OUTPUT_DIR/radon/code_complexity_$TIMESTAMP.md"

    echo "# Code Complexity Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Radon  " >>"$output_file"
    echo "**Complexity Threshold:** $COMPLEXITY_THRESHOLD (C=moderate, higher is worse)  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"
    echo "## Complexity Analysis" >>"$output_file"
    echo "" >>"$output_file"
    echo "\`\`\`" >>"$output_file"

    run_with_error_handling "radon" "Analyzing code complexity (threshold >= $COMPLEXITY_THRESHOLD)" \
      "radon cc $BACKEND_ROOT $RADON_OPTS -n $COMPLEXITY_THRESHOLD >> '$output_file'" \
      "$output_file"

    echo "\`\`\`" >>"$output_file"
    ;;

  "prospector")
    mkdir -p "$OUTPUT_DIR/prospector"

    json_file="$OUTPUT_DIR/prospector/comprehensive_analysis_$TIMESTAMP.json"
    md_file="$OUTPUT_DIR/prospector/comprehensive_analysis_$TIMESTAMP.md"

    run_with_error_handling "prospector" "Running comprehensive code analysis" \
      "timeout 60 prospector $BACKEND_ROOT $PROSPECTOR_OPTS --output-format json > '$json_file'" \
      "$json_file"

    # Convert JSON to markdown for AI consumption
    if [ -f "$json_file" ]; then
      echo "# Comprehensive Code Analysis Report" >"$md_file"
      echo "" >>"$md_file"
      echo "**Tool:** Prospector  " >>"$md_file"
      echo "**Generated:** $(date)  " >>"$md_file"
      echo "" >>"$md_file"
      echo "## Analysis Results" >>"$md_file"
      echo "" >>"$md_file"
      echo "\`\`\`json" >>"$md_file"
      cat "$json_file" >>"$md_file"
      echo "\`\`\`" >>"$md_file"
    fi
    ;;

  "pdoc")
    mkdir -p "$OUTPUT_DIR/pdoc"

    # Generate structured documentation
    run_with_error_handling "pdoc" "Generating API documentation from docstrings" \
      "timeout 60 pdoc $BACKEND_ROOT/app $PDOC_OPTS -o '$OUTPUT_DIR/pdoc'" \
      "$OUTPUT_DIR/pdoc"

    # Generate consolidated markdown file
    consolidated_file="$OUTPUT_DIR/pdoc/api_documentation_consolidated_$TIMESTAMP.md"
    run_with_error_handling "pdoc" "Creating consolidated documentation file" \
      "timeout 60 pdoc $BACKEND_ROOT/app $PDOC_OPTS > '$consolidated_file'" \
      "$consolidated_file"
    ;;

  "tbls")
    mkdir -p "$OUTPUT_DIR/tbls"

    # Load .env file if it exists
    if [ -f .env ]; then
      set -a
      source .env
      set +a
    fi

    if [ -z "$DATABASE_URL" ]; then
      echo "     ⚠️  DATABASE_URL not set. Skipping database schema generation."
      echo "        Set DATABASE_URL in .env file to enable this feature."
      RESULTS+=("tbls|false||DATABASE_URL not configured|")
    else
      # Create tbls config
      tbls_config=".tbls_temp.yml"
      cat >"$tbls_config" <<EOF
dsn: "$DATABASE_URL"
docPath: "$OUTPUT_DIR/tbls/docs"
EOF

      run_with_error_handling "tbls" "Generating database schema diagrams" \
        "tbls doc -c '$tbls_config' $TBLS_OPTS" \
        "$OUTPUT_DIR/tbls/docs"

      # Convert DOT to images if generated
      dot_file="$OUTPUT_DIR/tbls/docs/schema.dot"
      if [ -f "$dot_file" ]; then
        base_name="$OUTPUT_DIR/tbls/database_schema_$TIMESTAMP"
        if [ "$GENERATE_SVG" = true ]; then
          dot -Tsvg "$dot_file" -o "${base_name}.svg" 2>/dev/null
        fi
        if [ "$GENERATE_PNG" = true ]; then
          dot -Tpng "$dot_file" -o "${base_name}.png" 2>/dev/null
        fi
        if [ "$GENERATE_DOT" = false ]; then
          rm -rf "$OUTPUT_DIR/tbls/docs"
        fi
      fi

      rm -f "$tbls_config"
    fi
    ;;

  "filetree")
    mkdir -p "$OUTPUT_DIR/filetree"

    # Generate file tree with exclusions
    tree_file="$OUTPUT_DIR/filetree/project_structure_$TIMESTAMP.txt"

    run_with_error_handling "filetree" "Generating project file tree structure" \
      "tree -a -I 'venv|__pycache__|*.pyc|.git|node_modules|data|_architecture|*.log|.DS_Store|*.tmp|.pytest_cache|.coverage|htmlcov|dist|build|*.egg-info|.mypy_cache|.ruff_cache|.next|out|coverage|junit.xml|test-results|playwright-report|pnpm-lock.yaml|*.lock|*.tsbuildinfo' --dirsfirst --filesfirst -o '$tree_file'" \
      "$tree_file"

    # Also generate a markdown version for better AI consumption
    md_file="$OUTPUT_DIR/filetree/project_structure_$TIMESTAMP.md"
    echo "# Project File Structure" >"$md_file"
    echo "" >>"$md_file"
    echo "**Generated:** $(date)" >>"$md_file"
    echo "" >>"$md_file"
    echo "\`\`\`" >>"$md_file"
    cat "$tree_file" >>"$md_file" 2>/dev/null || echo "Failed to read tree output" >>"$md_file"
    echo "\`\`\`" >>"$md_file"
    ;;

  "alembic")
    mkdir -p "$OUTPUT_DIR/alembic"
    output_file="$OUTPUT_DIR/alembic/migration_analysis_$TIMESTAMP.md"

    echo "# Database Migration Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Alembic Migration Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    if [ -d "$BACKEND_ROOT/alembic" ]; then
      echo "## Migration History" >>"$output_file"
      echo "" >>"$output_file"

      cd "$BACKEND_ROOT"
      run_with_error_handling "alembic" "Analyzing migration history" \
        "alembic history --verbose >> '$OUTPUT_DIR/alembic/migration_analysis_$TIMESTAMP.md'" \
        "$output_file"

      echo "" >>"$output_file"
      echo "## Current Database State" >>"$output_file"
      echo "" >>"$output_file"

      run_with_error_handling "alembic" "Checking current database state" \
        "alembic current --verbose >> '$OUTPUT_DIR/alembic/migration_analysis_$TIMESTAMP.md'" \
        "$output_file"

      cd ..
    else
      echo "⚠️  No alembic directory found in $BACKEND_ROOT" >>"$output_file"
    fi
    ;;

  "typescript")
    mkdir -p "$OUTPUT_DIR/typescript"
    output_file="$OUTPUT_DIR/typescript/type_analysis_$TIMESTAMP.md"

    echo "# TypeScript Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** TypeScript Compiler (tsc)  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    if [ -f "$TSCONFIG_JSON" ]; then
      echo "## Type Checking Results" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`" >>"$output_file"

      run_with_error_handling "typescript" "Running TypeScript type checking" \
        "tsc $TYPESCRIPT_OPTS >> '$output_file' 2>&1" \
        "$output_file"

      echo "\`\`\`" >>"$output_file"

      # TypeScript configuration analysis
      echo "" >>"$output_file"
      echo "## TypeScript Configuration" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`json" >>"$output_file"
      cat "$TSCONFIG_JSON" >>"$output_file"
      echo "\`\`\`" >>"$output_file"
    else
      echo "⚠️  No tsconfig.json found in project root" >>"$output_file"
    fi
    ;;

  # COMMENTED OUT: ESLint tool
  # "eslint")
  #   mkdir -p "$OUTPUT_DIR/eslint"
  #   output_file="$OUTPUT_DIR/eslint/linting_analysis_$TIMESTAMP.md"
  #   json_file="$OUTPUT_DIR/eslint/linting_results_$TIMESTAMP.json"
  #
  #   echo "# ESLint Analysis Report" >"$output_file"
  #   echo "" >>"$output_file"
  #   echo "**Tool:** ESLint  " >>"$output_file"
  #   echo "**Generated:** $(date)  " >>"$output_file"
  #   echo "" >>"$output_file"
  #
  #   if [ -d "$FRONTEND_ROOT" ]; then
  #     echo "## Linting Results" >>"$output_file"
  #     echo "" >>"$output_file"
  #
  #     run_with_error_handling "eslint" "Running ESLint analysis" \
  #       "eslint $FRONTEND_COMPONENTS_PATHS $ESLINT_OPTS > '$json_file' 2>&1" \
  #       "$json_file"
  #
  #     # Convert JSON results to readable format
  #     if [ -f "$json_file" ]; then
  #       echo "\`\`\`json" >>"$output_file"
  #       cat "$json_file" >>"$output_file"
  #       echo "\`\`\`" >>"$output_file"
  #     fi
  #
  #     # Also get a summary in text format
  #     echo "" >>"$output_file"
  #     echo "## Summary" >>"$output_file"
  #     echo "" >>"$output_file"
  #     echo "\`\`\`" >>"$output_file"
  #
  #     run_with_error_handling "eslint" "Getting ESLint summary" \
  #       "eslint $FRONTEND_COMPONENTS_PATHS --format compact >> '$output_file' 2>&1" \
  #       "$output_file"
  #
  #     echo "\`\`\`" >>"$output_file"
  #   else
  #     echo "⚠️  No frontend source directory found at $FRONTEND_ROOT" >>"$output_file"
  #   fi
  #   ;;

  "nextjs")
    mkdir -p "$OUTPUT_DIR/nextjs"
    output_file="$OUTPUT_DIR/nextjs/nextjs_analysis_$TIMESTAMP.md"

    echo "# Next.js Project Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Next.js Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    if [ -f "$NEXT_CONFIG" ]; then
      echo "## Next.js Configuration" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`javascript" >>"$output_file"
      cat "$NEXT_CONFIG" >>"$output_file"
      echo "\`\`\`" >>"$output_file"
    fi

    if [ -f "$PACKAGE_JSON" ]; then
      echo "" >>"$output_file"
      echo "## Build Scripts Analysis" >>"$output_file"
      echo "" >>"$output_file"

      run_with_error_handling "nextjs" "Analyzing Next.js build configuration" \
        "node -e \"const pkg = require('./package.json'); console.log('Scripts:', JSON.stringify(pkg.scripts, null, 2)); console.log('Next.js dependencies:', JSON.stringify(Object.keys(pkg.dependencies || {}).filter(dep => dep.includes('next')), null, 2));\" >> '$output_file'" \
        "$output_file"
    fi

    # Analyze page structure
    if [ -d "$FRONTEND_ROOT/app" ]; then
      echo "" >>"$output_file"
      echo "## Page Structure (App Router)" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`" >>"$output_file"
      find "$FRONTEND_ROOT/app" -name "*.tsx" -o -name "*.ts" | head -20 >>"$output_file"
      echo "\`\`\`" >>"$output_file"
    fi
    ;;

  "tailwind")
    mkdir -p "$OUTPUT_DIR/tailwind"
    output_file="$OUTPUT_DIR/tailwind/tailwind_analysis_$TIMESTAMP.md"

    echo "# Tailwind CSS Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Tailwind CSS Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    if [ -f "$TAILWIND_CONFIG" ]; then
      echo "## Tailwind Configuration" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`typescript" >>"$output_file"
      cat "$TAILWIND_CONFIG" >>"$output_file"
      echo "\`\`\`" >>"$output_file"
    fi

    # Analyze Tailwind usage in components
    if [ -d "$FRONTEND_ROOT" ]; then
      echo "" >>"$output_file"
      echo "## Tailwind Class Usage Analysis" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`" >>"$output_file"

      run_with_error_handling "tailwind" "Analyzing Tailwind class usage" \
        "grep -r \"className=\" $FRONTEND_COMPONENTS_PATHS | head -20 >> '$output_file' 2>&1" \
        "$output_file"

      echo "\`\`\`" >>"$output_file"
    fi
    ;;

  "packagejson")
    mkdir -p "$OUTPUT_DIR/packagejson"
    output_file="$OUTPUT_DIR/packagejson/dependency_analysis_$TIMESTAMP.md"

    echo "# Package.json Dependency Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Package.json Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    if [ -f "$PACKAGE_JSON" ]; then
      echo "## Dependencies Overview" >>"$output_file"
      echo "" >>"$output_file"

      run_with_error_handling "packagejson" "Analyzing package.json dependencies" \
        "node -e \"const pkg = require('./package.json'); console.log('## Production Dependencies'); console.log(JSON.stringify(pkg.dependencies, null, 2)); console.log('## Development Dependencies'); console.log(JSON.stringify(pkg.devDependencies, null, 2)); console.log('## Scripts'); console.log(JSON.stringify(pkg.scripts, null, 2));\" >> '$output_file'" \
        "$output_file"

      # Security audit
      echo "" >>"$output_file"
      echo "## Security Audit" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`" >>"$output_file"

      run_with_error_handling "packagejson" "Running npm security audit" \
        "npm audit --audit-level moderate >> '$output_file' 2>&1" \
        "$output_file"

      echo "\`\`\`" >>"$output_file"

      # Outdated packages
      echo "" >>"$output_file"
      echo "## Outdated Packages" >>"$output_file"
      echo "" >>"$output_file"
      echo "\`\`\`" >>"$output_file"

      run_with_error_handling "packagejson" "Checking for outdated packages" \
        "npm outdated >> '$output_file' 2>&1" \
        "$output_file"

      echo "\`\`\`" >>"$output_file"
    else
      echo "⚠️  No package.json found in project root" >>"$output_file"
    fi
    ;;

  "env-analysis")
    mkdir -p "$OUTPUT_DIR/env-analysis"
    output_file="$OUTPUT_DIR/env-analysis/environment_analysis_$TIMESTAMP.md"

    echo "# Environment Configuration Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Environment Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    echo "## Environment Files Found" >>"$output_file"
    echo "" >>"$output_file"

    for env_file in ".env" ".env.local" ".env.example" ".env.production" ".env.development"; do
      if [ -f "$env_file" ]; then
        echo "### $env_file" >>"$output_file"
        echo "" >>"$output_file"
        echo "\`\`\`" >>"$output_file"
        # Show structure but mask sensitive values
        sed 's/=.*/=***MASKED***/' "$env_file" >>"$output_file"
        echo "\`\`\`" >>"$output_file"
        echo "" >>"$output_file"
      fi
    done

    # Analyze environment variable usage in code
    echo "## Environment Variable Usage in Code" >>"$output_file"
    echo "" >>"$output_file"
    echo "\`\`\`" >>"$output_file"

    run_with_error_handling "env-analysis" "Analyzing environment variable usage" \
      "grep -r \"process.env\\|os.environ\" $FRONTEND_ROOT $BACKEND_ROOT | head -20 >> '$output_file' 2>&1" \
      "$output_file"

    echo "\`\`\`" >>"$output_file"
    ;;

  # COMMENTED OUT: Docker tool
  # "docker")
  #   mkdir -p "$OUTPUT_DIR/docker"
  #   output_file="$OUTPUT_DIR/docker/docker_analysis_$TIMESTAMP.md"
  #
  #   echo "# Docker Configuration Analysis Report" >"$output_file"
  #   echo "" >>"$output_file"
  #   echo "**Tool:** Docker Analysis  " >>"$output_file"
  #   echo "**Generated:** $(date)  " >>"$output_file"
  #   echo "" >>"$output_file"
  #
  #   # Check for Docker files
  #   docker_files_found=false
  #   for docker_file in "Dockerfile" "docker-compose.yml" "docker-compose.yaml" ".dockerignore"; do
  #     if [ -f "$docker_file" ]; then
  #       docker_files_found=true
  #       echo "### $docker_file" >>"$output_file"
  #       echo "" >>"$output_file"
  #       echo "\`\`\`" >>"$output_file"
  #       cat "$docker_file" >>"$output_file"
  #       echo "\`\`\`" >>"$output_file"
  #       echo "" >>"$output_file"
  #     fi
  #   done
  #
  #   if [ "$docker_files_found" = false ]; then
  #     echo "⚠️  No Docker configuration files found in project root" >>"$output_file"
  #   else
  #     run_with_error_handling "docker" "Docker configuration analysis completed" \
  #       "echo 'Docker files analyzed successfully'" \
  #       "$output_file"
  #   fi
  #   ;;

  "api-contracts")
    mkdir -p "$OUTPUT_DIR/api-contracts"
    output_file="$OUTPUT_DIR/api-contracts/api_contracts_$TIMESTAMP.md"

    echo "# API Contract Analysis Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** API Contract Validation  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    # Create a Python script to analyze API contracts
    cat >api_contract_analyzer.py <<'EOF'
import json
import os
import re
from pathlib import Path

def analyze_api_contracts():
    print("# API Contract Analysis")
    print("")
    
    # Look for API calls in frontend
    frontend_api_calls = []
    if os.path.exists('src'):
        for file_path in Path('src').rglob('*.tsx'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find fetch calls and API endpoints
                fetch_calls = re.findall(r'fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
                axios_calls = re.findall(r'\.(?:get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
                
                for call in fetch_calls + axios_calls:
                    if call.startswith('/api/') or call.startswith('http'):
                        frontend_api_calls.append({
                            'file': str(file_path),
                            'endpoint': call
                        })
    
    print("## Frontend API Calls Found")
    print("")
    for call in frontend_api_calls[:20]:  # Limit to first 20
        print(f"- **{call['endpoint']}** (in {call['file']})")
    
    # Look for FastAPI routes in backend
    backend_routes = []
    if os.path.exists('backend/app'):
        for file_path in Path('backend/app').rglob('*.py'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find FastAPI route decorators
                routes = re.findall(r'@router\.(?:get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
                app_routes = re.findall(r'@app\.(?:get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]', content)
                
                for route in routes + app_routes:
                    backend_routes.append({
                        'file': str(file_path),
                        'endpoint': route
                    })
    
    print("")
    print("## Backend API Routes Found")
    print("")
    for route in backend_routes[:20]:  # Limit to first 20
        print(f"- **{route['endpoint']}** (in {route['file']})")

    print("")
    print("## Contract Analysis Summary")
    print("")
    print(f"- Frontend API calls found: {len(frontend_api_calls)}")
    print(f"- Backend API routes found: {len(backend_routes)}")

if __name__ == "__main__":
    analyze_api_contracts()
EOF

    run_with_error_handling "api-contracts" "Analyzing API contracts between frontend and backend" \
      "python api_contract_analyzer.py >> '$output_file'" \
      "$output_file"

    rm -f api_contract_analyzer.py
    ;;

  "type-sync")
    mkdir -p "$OUTPUT_DIR/type-sync"
    output_file="$OUTPUT_DIR/type-sync/type_sync_$TIMESTAMP.md"

    echo "# Pydantic-TypeScript Type Synchronization Report" >"$output_file"
    echo "" >>"$output_file"
    echo "**Tool:** Type Synchronization Analysis  " >>"$output_file"
    echo "**Generated:** $(date)  " >>"$output_file"
    echo "" >>"$output_file"

    # Create a Python script to analyze type synchronization
    cat >type_sync_analyzer.py <<'EOF'
import os
import re
from pathlib import Path

def analyze_type_sync():
    print("# Type Synchronization Analysis")
    print("")
    
    # Find Pydantic models in backend
    pydantic_models = []
    if os.path.exists('backend/app'):
        for file_path in Path('backend/app').rglob('*.py'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find Pydantic BaseModel classes
                models = re.findall(r'class\s+(\w+)\s*\([^)]*BaseModel[^)]*\):', content)
                for model in models:
                    pydantic_models.append({
                        'name': model,
                        'file': str(file_path)
                    })
    
    print("## Pydantic Models Found")
    print("")
    for model in pydantic_models:
        print(f"- **{model['name']}** (in {model['file']})")
    
    # Find TypeScript interfaces in frontend
    typescript_interfaces = []
    if os.path.exists('src'):
        for file_path in Path('src').rglob('*.ts'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find TypeScript interfaces
                interfaces = re.findall(r'interface\s+(\w+)', content)
                types = re.findall(r'type\s+(\w+)', content)
                for interface in interfaces + types:
                    typescript_interfaces.append({
                        'name': interface,
                        'file': str(file_path)
                    })
    
    print("")
    print("## TypeScript Interfaces/Types Found")
    print("")
    for interface in typescript_interfaces:
        print(f"- **{interface['name']}** (in {interface['file']})")

    print("")
    print("## Type Synchronization Summary")
    print("")
    print(f"- Pydantic models found: {len(pydantic_models)}")
    print(f"- TypeScript interfaces/types found: {len(typescript_interfaces)}")
    
    # Look for potential matches
    pydantic_names = {model['name'] for model in pydantic_models}
    typescript_names = {interface['name'] for interface in typescript_interfaces}
    
    matches = pydantic_names.intersection(typescript_names)
    if matches:
        print("")
        print("## Potential Type Matches")
        print("")
        for match in matches:
            print(f"- **{match}** (found in both Pydantic and TypeScript)")

if __name__ == "__main__":
    analyze_type_sync()
EOF

    run_with_error_handling "type-sync" "Analyzing type synchronization between Pydantic and TypeScript" \
      "python type_sync_analyzer.py >> '$output_file'" \
      "$output_file"

    rm -f type_sync_analyzer.py
    ;;
  esac
done

# === GENERATE FINAL REPORT ===

echo -e "\n📊 Generating final report summary..."
generate_report_summary

echo -e "\n🎉 Comprehensive full-stack architecture analysis complete!"
echo "📁 All files saved to: $OUTPUT_DIR"
echo "📄 Summary report: $OUTPUT_DIR/REPORT_SUMMARY.md"
echo -e "\nGenerated folders:"
for dir in "$OUTPUT_DIR"/*; do
  if [ -d "$dir" ]; then
    echo "  📂 $(basename "$dir")"
  fi
done
