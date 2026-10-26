// Central labels, severity styling, and plain-English explanation formatting

export const FLAG_TYPE_LABELS = {
  redundant_sentences: "Redundant Sentences",
  repeated_content: "Repeated Content",
  verbose_for_template: "Verbose Template Outlier",
};

export const SEVERITY_COLORS = {
  high: { bg: "#fee2e2", text: "#991b1b", border: "#f87171" },
  medium: { bg: "#fef3c7", text: "#92400e", border: "#f59e0b" },
  low: { bg: "#dbeafe", text: "#1e40af", border: "#60a5fa" },
};

/**
 * Returns plain-English explanations parsed from the flag's detail field.
 * Safely handles string or parsed object and provides generic fallbacks for missing/unparseable data.
 */
export function getPlainEnglishFlagExplanation(flag) {
  if (!flag) return "No flag details available.";

  let detail = flag.detail;
  if (typeof detail === "string") {
    try {
      detail = JSON.parse(detail);
    } catch {
      detail = null;
    }
  }

  const type = flag.flag_type;

  // 1. Redundant Sentences
  if (type === "redundant_sentences") {
    if (detail && Array.isArray(detail.duplicates) && detail.duplicates.length > 0) {
      const parts = detail.duplicates.map((d, i) => {
        const dupNum = (d.duplicate_index != null ? d.duplicate_index + 1 : "?");
        const origNum = (d.original_index != null ? d.original_index + 1 : "?");
        if (d.type === "exact") {
          return `Sentence ${dupNum} is an exact duplicate of sentence ${origNum}.`;
        }
        const sim = d.similarity != null ? Number(d.similarity).toFixed(2) : "0.90+";
        return `Sentence ${dupNum} is a near-duplicate of sentence ${origNum} (similarity ${sim}).`;
      });
      let summaryText = parts.join(" ");
      if (detail.total_estimated_wasted_tokens != null) {
        summaryText += ` Estimated wasted tokens: ${detail.total_estimated_wasted_tokens}`;
        if (detail.wasted_percentage != null) {
          summaryText += ` (${detail.wasted_percentage}% of prompt).`;
        } else {
          summaryText += ".";
        }
      }
      return summaryText;
    }
    return "This prompt contains duplicate or near-duplicate sentences that can be removed without losing meaning.";
  }

  // 2. Repeated Content
  if (type === "repeated_content") {
    if (detail && Array.isArray(detail.findings) && detail.findings.length > 0) {
      const parts = detail.findings.map(f => {
        if (f.type === "consecutive_blank_lines") {
          return `Contains ${f.count} consecutive blank lines.`;
        }
        if (f.type === "consecutive_spaces") {
          return `Contains ${f.count} consecutive spaces.`;
        }
        if (f.type === "repeated_words") {
          return `Word "${f.word || 'word'}" is repeated ${f.count} times in a row.`;
        }
        return "Contains repetitive formatting characters.";
      });
      let summaryText = parts.join(" ");
      if (detail.total_estimated_wasted_tokens != null) {
        summaryText += ` Estimated wasted tokens: ${detail.total_estimated_wasted_tokens}.`;
      }
      return summaryText;
    }
    return "This prompt contains excessive blank lines, runs of spaces, or repeated words.";
  }

  // 3. Verbose Template Outlier
  if (type === "verbose_for_template") {
    if (detail && detail.ratio != null) {
      const ratio = Number(detail.ratio).toFixed(1);
      const reqTokens = detail.request_input_tokens ?? "many";
      const minTokens = detail.min_input_tokens ?? "baseline";
      const grpSize = detail.group_size ?? "multiple";
      return `Prompt used ${reqTokens} tokens, which is ${ratio}x the template baseline (${minTokens} tokens across ${grpSize} similar requests).`;
    }
    return "This prompt is significantly more verbose than other requests sharing the same initial template signature.";
  }

  // Generic Fallback
  return `Flagged as ${FLAG_TYPE_LABELS[type] || type}.`;
}

/**
 * Returns honest status badge text and styling for suggestions.
 */
export function getStatusBadgeInfo(suggestion) {
  if (!suggestion) return null;

  const { status, method, optimizer_model, similarity_score } = suggestion;

  if (status === "ok") {
    if (method === "rule_based") {
      return {
        label: "Rule-based cleanup: only removes text the analyzer flagged. Not checked against a model.",
        type: "success",
        bgColor: "#dcfce7",
        textColor: "#166534",
        borderColor: "#86efac",
      };
    }
    const model = optimizer_model || "optimizer";
    const sim = similarity_score != null ? Number(similarity_score).toFixed(2) : "0.85+";
    return {
      label: `Verified on ${model}: similarity ${sim}`,
      type: "success",
      bgColor: "#dcfce7",
      textColor: "#166534",
      borderColor: "#86efac",
    };
  }

  if (status === "not_verified_safe") {
    const sim = similarity_score != null ? Number(similarity_score).toFixed(2) : "<0.85";
    return {
      label: `Not verified safe: similarity ${sim}. Review before using.`,
      type: "warning",
      bgColor: "#fef3c7",
      textColor: "#92400e",
      borderColor: "#f59e0b",
    };
  }

  if (status === "no_change") {
    return {
      label: "Nothing to remove.",
      type: "neutral",
      bgColor: "#f3f4f6",
      textColor: "#374151",
      borderColor: "#d1d5db",
    };
  }

  if (status === "disabled") {
    return {
      label: "LLM rewriting is disabled. Set ENABLE_LLM_REWRITE=true on the backend to enable.",
      type: "neutral",
      bgColor: "#f3f4f6",
      textColor: "#4b5563",
      borderColor: "#d1d5db",
    };
  }

  if (status === "failed") {
    return {
      label: suggestion.message || "Rewrite call failed.",
      type: "error",
      bgColor: "#fee2e2",
      textColor: "#991b1b",
      borderColor: "#f87171",
    };
  }

  return {
    label: status,
    type: "neutral",
    bgColor: "#f3f4f6",
    textColor: "#374151",
    borderColor: "#d1d5db",
  };
}
