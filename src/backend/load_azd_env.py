"""Load environment variables from AZD for local development."""
import os
import subprocess
from io import StringIO
from dotenv import load_dotenv

def load_azd_environment():
    """Load environment variables from azd env get-values or fallback to .env file."""
    
    # In production (Azure Container Apps), environment variables are already injected
    # Check if we're running in Azure by looking for typical Azure env vars
    if os.getenv("WEBSITE_SITE_NAME") or os.getenv("CONTAINER_APP_NAME") or os.getenv("AZURE_CLIENT_ID"):
        print("✓ Running in Azure - using platform-injected environment variables")
        return
    
    # Try azd env get-values for local development
    try:
        result = subprocess.run(
            ["azd", "env", "get-values"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout:
            load_dotenv(stream=StringIO(result.stdout))
            print("✓ Loaded environment from azd env get-values")
            return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Try specific azd environment file
    azd_env_file = os.path.join(
        os.path.dirname(__file__), "..", ".azure", "RTagentFastAPI", ".env"
    )
    if os.path.exists(azd_env_file):
        load_dotenv(azd_env_file)
        print(f"✓ Loaded environment from {azd_env_file}")
        return
    
    # Final fallback to .env in current directory
    if os.path.exists(".env"):
        load_dotenv(".env")
        print("✓ Loaded environment from .env")
        return
    
    print("⚠ No environment file found - using system environment variables")

def override_keyvault_references():
    """Override Key Vault references with direct values for local development."""
    
    ai_services_key = os.getenv("AZURE_AI_SERVICES_KEY", "")
    if ai_services_key.startswith("@Microsoft.KeyVault"):
        print("⚠ AZURE_AI_SERVICES_KEY is a Key Vault reference. You need to set the direct key for local development.")
        print("  Get it from: Azure Portal -> AI Services -> Keys and Endpoint")
        print("  Set it with: $env:AZURE_AI_SERVICES_KEY=\"your-actual-key\"")
        # Don't override with empty - let the error bubble up

if __name__ == "__main__":
    load_azd_environment()
