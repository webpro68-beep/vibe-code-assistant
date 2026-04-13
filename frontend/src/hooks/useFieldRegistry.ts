"use client";

import { useCallback, useRef } from "react";

export function useFieldRegistry() {
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});

  const registerField = useCallback(
    (key: string) => (node: HTMLElement | null) => {
      fieldRefs.current[key] = node;
    },
    [],
  );

  const scrollToField = useCallback((key: string) => {
    const node = fieldRefs.current[key];
    if (!node) return false;

    node.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });

    if ("focus" in node && typeof node.focus === "function") {
      window.setTimeout(() => {
        node.focus();
      }, 150);
    }

    return true;
  }, []);

  return {
    registerField,
    scrollToField,
  };
}