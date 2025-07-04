from pycopilot import AuthCache
from jira_utils import write_issue_for_chat

class CopilotChat:
    def __init__(self):
        self.auth = AuthCache()

    def ask_with_reauth(self, prompt, stream=False, client=None, max_reauth=1):
        from pycopilot import AuthenticationError
        reauths = 0
        if client is None:
            client = self.auth.authenticate()
        while True:
            try:
                if stream:
                    for chunk in client.ask(prompt, stream=True):
                        yield chunk
                    break
                else:
                    return client.ask(prompt, stream=False)
            except AuthenticationError:
                if reauths < max_reauth:
                    client = self.auth.authenticate()
                    reauths += 1
                    continue
                else:
                    raise

    def chat_with_issues(self, issues, jira, initial_user_message=None):
        import tempfile
        import os
        client = self.auth.authenticate()
        temp_files = []
        try:
            for issue in issues:
                issue_content = write_issue_for_chat(issue, jira)
                try:
                    client.add_context(issue_content)
                except Exception:
                    with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{issue.key}.txt', delete=False) as f:
                        f.write(issue_content)
                        temp_file = f.name
                        temp_files.append(temp_file)
                    client.add_context(temp_file)
            return client, temp_files
        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except Exception:
                        pass

    def interactive_chat(self, client, initial_user_message=None):
        """Simple interactive chat loop for pycopilot, with reauth on 401 error, with colors, emojis, and markdown colorization."""
        try:
            from colorama import Fore, Style, init as colorama_init
            colorama_init(autoreset=True)
            COLORAMA = True
        except ImportError:
            COLORAMA = False
            Fore = Style = type('', (), {'RESET_ALL': '', 'BRIGHT': '', 'CYAN': '', 'GREEN': '', 'YELLOW': '', 'RED': '', 'MAGENTA': '', 'WHITE': ''})()

        import re
        def c(text, color):
            return f"{color}{text}{Style.RESET_ALL}" if COLORAMA else text

        def colorize_markdown(line):
            # Code block (simple, not multi-line)
            if line.strip().startswith('```'):
                return c(line, Fore.GREEN + Style.BRIGHT)
            # Headers (skip bold for headers)
            if re.match(r"^# ", line):
                return c(line, Fore.MAGENTA + Style.BRIGHT)
            if re.match(r"^## ", line):
                return c(line, Fore.CYAN + Style.BRIGHT)
            if re.match(r"^### ", line):
                return c(line, Fore.BLUE + Style.BRIGHT)
            # Inline formatting for non-headers
            # Bold
            line = re.sub(r"\*\*(.*?)\*\*", lambda m: c(m.group(1), Fore.YELLOW + Style.BRIGHT), line)
            # Italic (avoid matching inside bold)
            line = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?!\*)", lambda m: c(m.group(1), Fore.GREEN), line)
            # Inline code
            line = re.sub(r"`([^`]+)`", lambda m: c(m.group(1), Fore.CYAN), line)
            # Lists (after inline formatting)
            if re.match(r"^\s*\d+\. ", line):
                return c(line, Fore.WHITE)
            if re.match(r"^\s*[-*] ", line):
                return c(line, Fore.WHITE)
            return line

        assistant_emoji = "🤖"
        user_emoji = "🧑"
        system_emoji = "⚙️"
        error_emoji = "❌"
        reauth_emoji = "🔑"

        print(c(f"=== {assistant_emoji} Copilot Chat ===", Fore.CYAN))
        print(c(f"Type 'quit' or 'exit' to end the chat session", Fore.YELLOW))
        print(c(f"Context: Issues have been added to the conversation", Fore.GREEN))
        print(c("-" * 50, Fore.MAGENTA))
        
        first_message = True
        while True:
            try:
                if first_message and initial_user_message:
                    user_input = initial_user_message.strip()
                    first_message = False
                else:
                    user_input = input(c(f"\n{user_emoji} You: ", Fore.YELLOW)).strip()
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                if not user_input:
                    continue
                print(c(f"{assistant_emoji} Assistant: ", Fore.CYAN), end="", flush=True)
                # Stream the response, with reauth on 401
                def stream_and_colorize():
                    buffer = ""
                    try:
                        for chunk in self.ask_with_reauth(user_input, stream=True, client=client):
                            buffer += chunk
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                print(colorize_markdown(line), flush=True)
                        if buffer:
                            print(colorize_markdown(buffer), flush=True)
                    except Exception as e:
                        print(c(f"{error_emoji} Error getting response: {e}", Fore.RED))
                try:
                    stream_and_colorize()
                except Exception as e:
                    print(c(f"{error_emoji} Error getting response: {e}", Fore.RED))
            except KeyboardInterrupt:
                print(c(f"\n\n{system_emoji} Chat session ended.", Fore.MAGENTA))
                break
            except EOFError:
                print(c(f"\n{system_emoji} Chat session ended.", Fore.MAGENTA))
                break
