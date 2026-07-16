"""Text processing utilities for message content.

Provides deterministic cleaning of email replies and forwarded messages
before they are sent to the LLM, reducing context length and preventing
false positives from quoted commitments.
"""

import re

def strip_quoted_content(text: str) -> str:
    """Strip quoted reply chains and forwarded content from emails.
    
    Removes:
    - Lines starting with `>` (standard email quoting)
    - Content after `On [date], [person] wrote:`
    - Content after `---------- Forwarded message ---------`
    - Content after `From: ...` in forwards
    """
    if not text:
        return text

    # Remove standard `>` quoted lines
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith(">"):
            continue
        cleaned_lines.append(line)
    
    text = "\n".join(cleaned_lines)

    # Cut off at "On ... wrote:" patterns
    on_wrote_pattern = r"(?i)\n*On\s+.*?,.*?\s+wrote:\s*\n*"
    text = re.split(on_wrote_pattern, text)[0]

    # Cut off at forwarded message headers
    forward_pattern = r"(?i)\n*---------- Forwarded message ---------\n*"
    text = re.split(forward_pattern, text)[0]
    
    # Cut off at "From: " blocks that typically start a forwarded/replied thread
    # Needs to match From:, Date:, Subject:, To: blocks
    from_block_pattern = r"(?i)\n*From:\s+.*?\nDate:\s+.*?\n"
    text = re.split(from_block_pattern, text)[0]

    return text.strip()
