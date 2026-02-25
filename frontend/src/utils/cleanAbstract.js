/**
 * Strip JATS/XML tags from abstract text, converting semantic tags
 * to plain-text equivalents and collapsing whitespace.
 *
 * Crossref returns abstracts with JATS XML markup (e.g. <jats:p>, <jats:sub>).
 * This function strips all of it for clean display.
 */
export default function cleanAbstract(raw) {
  if (!raw) return '';
  let text = raw;
  // Remove entire sections that are just labels (e.g. "Abstract", "Graphic abstract")
  text = text.replace(/<jats:title>\s*(Abstract|Graphic\s+abstract|Graphical\s+abstract)\s*<\/jats:title>/gi, '');
  // Convert meaningful inline tags to plain text
  text = text.replace(/<jats:sub>(.*?)<\/jats:sub>/gi, (_, c) => c);
  text = text.replace(/<jats:sup>(.*?)<\/jats:sup>/gi, (_, c) => c);
  text = text.replace(/<jats:italic>(.*?)<\/jats:italic>/gi, (_, c) => c);
  text = text.replace(/<jats:bold>(.*?)<\/jats:bold>/gi, (_, c) => c);
  text = text.replace(/<jats:sc>(.*?)<\/jats:sc>/gi, (_, c) => c);
  text = text.replace(/<ns4:bold>(.*?)<\/ns4:bold>/gi, (_, c) => c);
  // <jats:p> / <ns4:p> → paragraph break
  text = text.replace(/<jats:p>/gi, '\n\n');
  text = text.replace(/<\/jats:p>/gi, '');
  text = text.replace(/<ns4:p>/gi, '\n\n');
  text = text.replace(/<\/ns4:p>/gi, '');
  // Strip all remaining XML/HTML tags
  text = text.replace(/<[^>]+>/g, '');
  // Collapse whitespace
  text = text.replace(/\n{3,}/g, '\n\n').trim();
  return text;
}
