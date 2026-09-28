/**
 * AMAP UI Action Executor (frontend/worker/lib/uiActionExecutor.ts)
 *
 * Executes REAL application/UI actions at a viewport position:
 *  - leftClick:   dispatches real pointer/mouse/click events on the interactive
 *                 element under the position (real React handlers run).
 *  - rightClick:  dispatches contextmenu (and opens the AMAP gesture context
 *                 menu when no element consumes it).
 *  - doubleClick: dispatches a real dblclick sequence.
 *  - select:      focuses and visually selects the element.
 *  - scroll:      scrolls the real scrollable container under the position
 *                 (or the window), with throttling.
 *  - drag:        pointer-event driven drag of [data-amap-draggable] elements
 *                 onto [data-amap-drop-zone] targets, dispatching real
 *                 amapdrop events consumed by the task UI.
 *
 * Every executed action returns a descriptor used for backend audit events.
 */

export interface ActionTargetDescriptor {
  found: boolean;
  tag: string;
  role: string;
  text: string;
  actionId: string | null;
  interactive: boolean;
}

export interface ExecutedActionResult {
  ok: boolean;
  action: string;
  target: ActionTargetDescriptor;
  detail?: string;
}

const INTERACTIVE_SELECTOR =
  'button, a[href], input, select, textarea, label, summary, [role="button"], [role="tab"], [role="option"], [role="menuitem"], [role="switch"], [role="checkbox"], [role="link"], [contenteditable="true"], [tabindex]:not([tabindex="-1"])';

const DRAGGABLE_SELECTOR = '[data-amap-draggable="true"]';
const DROP_ZONE_SELECTOR = '[data-amap-drop-zone="true"]';

export function describeElement(el: Element | null): ActionTargetDescriptor {
  if (!el) {
    return { found: false, tag: '', role: '', text: '', actionId: null, interactive: false };
  }
  const interactive = el.matches(INTERACTIVE_SELECTOR);
  const role = el.getAttribute('role') || '';
  const text = (
    el.getAttribute('aria-label') ||
    el.textContent ||
    ''
  )
    .trim()
    .slice(0, 80);
  return {
    found: true,
    tag: el.tagName.toLowerCase(),
    role,
    text,
    actionId: el.getAttribute('data-amap-action-id'),
    interactive,
  };
}

/** Find the nearest interactive ancestor (or self) for a point. */
export function findInteractiveAt(x: number, y: number): HTMLElement | null {
  const el = document.elementFromPoint(x, y);
  if (!el) return null;
  if (el.matches(INTERACTIVE_SELECTOR)) return el as HTMLElement;
  const closest = el.closest(INTERACTIVE_SELECTOR);
  return (closest as HTMLElement) || null;
}

function fireMouseSequence(el: HTMLElement, x: number, y: number, types: string[]): void {
  for (const type of types) {
    const EventClass = type.startsWith('pointer') ? PointerEvent : MouseEvent;
    const event = new EventClass(type, {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: x,
      clientY: y,
      button: 0,
      buttons: type.endsWith('down') ? 1 : 0,
    });
    el.dispatchEvent(event);
  }
}

/** Left click a real element at viewport coordinates. */
export function leftClick(x: number, y: number): ExecutedActionResult {
  const target = findInteractiveAt(x, y);
  if (!target) {
    return {
      ok: false,
      action: 'left_click',
      target: describeElement(document.elementFromPoint(x, y)),
      detail: 'No interactive element at pointer position.',
    };
  }
  try {
    if (typeof target.focus === 'function') target.focus({ preventScroll: true });
  } catch {
    /* non-focusable */
  }
  fireMouseSequence(
    target,
    x,
    y,
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']
  );
  return { ok: true, action: 'left_click', target: describeElement(target) };
}

/** Double click a real element at viewport coordinates. */
export function doubleClick(x: number, y: number): ExecutedActionResult {
  const target = findInteractiveAt(x, y);
  if (!target) {
    return {
      ok: false,
      action: 'double_click',
      target: describeElement(document.elementFromPoint(x, y)),
      detail: 'No interactive element at pointer position.',
    };
  }
  try {
    if (typeof target.focus === 'function') target.focus({ preventScroll: true });
  } catch {
    /* non-focusable */
  }
  fireMouseSequence(target, x, y, ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']);
  fireMouseSequence(target, x, y, ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']);
  fireMouseSequence(target, x, y, ['dblclick']);
  return { ok: true, action: 'double_click', target: describeElement(target) };
}

/**
 * Right click at viewport coordinates. Dispatches a real contextmenu event;
 * when no handler consumes it, emits an 'amapcontextmenu' CustomEvent that
 * the workstation UI listens to in order to open the gesture context menu.
 */
export function rightClick(x: number, y: number): ExecutedActionResult {
  const el = (document.elementFromPoint(x, y) as HTMLElement) || document.body;
  const target = findInteractiveAt(x, y) || el;
  const contextEvent = new MouseEvent('contextmenu', {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y,
    button: 2,
  });
  const consumed = !target.dispatchEvent(contextEvent);
  if (!consumed) {
    // No application handler consumed it: open the AMAP gesture context menu.
    window.dispatchEvent(
      new CustomEvent('amapcontextmenu', { detail: { x, y, source: 'gesture' } })
    );
  }
  return {
    ok: true,
    action: 'right_click',
    target: describeElement(target),
    detail: consumed ? 'contextmenu consumed by element handler' : 'AMAP context menu opened',
  };
}

/** Select / focus the element under the pointer. */
export function selectItem(x: number, y: number): ExecutedActionResult {
  const target = findInteractiveAt(x, y) || (document.elementFromPoint(x, y) as HTMLElement | null);
  if (!target) {
    return {
      ok: false,
      action: 'select_item',
      target: describeElement(null),
      detail: 'No element at pointer position.',
    };
  }
  try {
    if (typeof target.focus === 'function') target.focus({ preventScroll: true });
  } catch {
    /* non-focusable */
  }
  target.setAttribute('data-amap-selected', 'true');
  window.dispatchEvent(
    new CustomEvent('amapselect', { detail: { target, x, y, source: 'gesture' } })
  );
  // Brief visual selection highlight
  window.setTimeout(() => {
    if (target.getAttribute('data-amap-selected') === 'true') {
      target.removeAttribute('data-amap-selected');
    }
  }, 1200);
  return { ok: true, action: 'select_item', target: describeElement(target) };
}

/**
 * Find the scrollable ancestor of the element at a position (or the window).
 */
function findScrollableAt(x: number, y: number): HTMLElement | null {
  let el = document.elementFromPoint(x, y) as HTMLElement | null;
  while (el && el !== document.body && el !== document.documentElement) {
    const style = window.getComputedStyle(el);
    const overflowY = style.overflowY;
    const scrollable = /(auto|scroll)/.test(overflowY) && el.scrollHeight > el.clientHeight + 4;
    if (scrollable) return el;
    el = el.parentElement;
  }
  return null;
}

/**
 * Scroll the application view. Returns the applied pixel delta (0 when
 * throttled or nothing to scroll).
 */
const lastScrollAt: Record<string, number> = {};

export function scrollView(
  direction: 'up' | 'down' | 'left' | 'right',
  amountPx: number,
  position: { x: number; y: number } | null,
  throttleMs = 120
): ExecutedActionResult {
  const now = Date.now();
  if (lastScrollAt[direction] && now - lastScrollAt[direction] < throttleMs) {
    return {
      ok: false,
      action: 'scroll',
      target: describeElement(null),
      detail: 'scroll throttled',
    };
  }
  lastScrollAt[direction] = now;

  const container = position ? findScrollableAt(position.x, position.y) : null;

  const amount = Math.max(40, Math.round(amountPx));
  if (container) {
    if (direction === 'up') container.scrollTop -= amount;
    else if (direction === 'down') container.scrollTop += amount;
    else if (direction === 'left') container.scrollLeft -= amount;
    else if (direction === 'right') container.scrollLeft += amount;
  } else {
    if (direction === 'up') window.scrollBy({ top: -amount, behavior: 'auto' });
    else if (direction === 'down') window.scrollBy({ top: amount, behavior: 'auto' });
    else if (direction === 'left') window.scrollBy({ left: -amount, behavior: 'auto' });
    else if (direction === 'right') window.scrollBy({ left: amount, behavior: 'auto' });
  }
  return {
    ok: true,
    action: `scroll_${direction}`,
    target: describeElement(container || document.body),
    detail: `${amount}px ${direction}`,
  };
}

// ---------------------------------------------------------------------------
// Drag: real pointer-driven dragging of [data-amap-draggable] elements
// ---------------------------------------------------------------------------

export interface DragSession {
  source: HTMLElement;
  ghost: HTMLElement;
  startX: number;
  startY: number;
  lastX: number;
  lastY: number;
  startedAt: number;
  pathPx: number;
  active: boolean;
}

let activeDrag: DragSession | null = null;

export function getActiveDrag(): DragSession | null {
  return activeDrag;
}

/** Begin a real drag of the draggable element at viewport coordinates. */
export function dragStart(x: number, y: number): ExecutedActionResult {
  const el = document.elementFromPoint(x, y);
  const draggable = (el?.closest(DRAGGABLE_SELECTOR) as HTMLElement) || null;
  if (!draggable) {
    return {
      ok: false,
      action: 'drag_start',
      target: describeElement(el),
      detail: 'No draggable element at pointer position.',
    };
  }
  if (activeDrag && activeDrag.active) {
    endActiveDrag(x, y, false);
  }

  const rect = draggable.getBoundingClientRect();
  const ghost = draggable.cloneNode(true) as HTMLElement;
  ghost.setAttribute('data-amap-drag-ghost', 'true');
  Object.assign(ghost.style, {
    position: 'fixed',
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
    margin: '0',
    zIndex: '99999',
    pointerEvents: 'none',
    opacity: '0.85',
    transform: 'scale(1.05)',
    transition: 'none',
  } as CSSStyleDeclaration);
  document.body.appendChild(ghost);

  activeDrag = {
    source: draggable,
    ghost,
    startX: x,
    startY: y,
    lastX: x,
    lastY: y,
    startedAt: Date.now(),
    pathPx: 0,
    active: true,
  };
  draggable.setAttribute('data-amap-dragging', 'true');
  draggable.dispatchEvent(
    new CustomEvent('amapdragstart', { detail: { x, y, source: 'gesture' }, bubbles: true })
  );
  return { ok: true, action: 'drag_start', target: describeElement(draggable) };
}

/** Move the active drag to viewport coordinates. */
export function dragMove(x: number, y: number): boolean {
  if (!activeDrag || !activeDrag.active) return false;
  activeDrag.pathPx += Math.hypot(x - activeDrag.lastX, y - activeDrag.lastY);
  activeDrag.lastX = x;
  activeDrag.lastY = y;
  const dx = x - activeDrag.startX;
  const dy = y - activeDrag.startY;
  activeDrag.ghost.style.transform = `translate(${dx}px, ${dy}px) scale(1.05)`;

  const zone = dropZoneAt(x, y);
  document.querySelectorAll('[data-amap-drop-hover="true"]').forEach((z) => {
    z.removeAttribute('data-amap-drop-hover');
    z.dispatchEvent(new CustomEvent('amapdropleave', { detail: { x, y } }));
  });
  if (zone) {
    if (zone.getAttribute('data-amap-drop-hover') !== 'true') {
      zone.setAttribute('data-amap-drop-hover', 'true');
      zone.dispatchEvent(new CustomEvent('amapdrophover', { detail: { x, y } }));
    }
  }
  activeDrag.source.dispatchEvent(
    new CustomEvent('amapdragmove', { detail: { x, y, source: 'gesture' }, bubbles: true })
  );
  return true;
}

function dropZoneAt(x: number, y: number): HTMLElement | null {
  const el = document.elementFromPoint(x, y);
  return (el?.closest(DROP_ZONE_SELECTOR) as HTMLElement) || null;
}

function endActiveDrag(x: number, y: number, dispatchDrop: boolean): ExecutedActionResult {
  const drag = activeDrag;
  if (!drag) {
    return {
      ok: false,
      action: 'drag_end',
      target: describeElement(null),
      detail: 'No active drag.',
    };
  }
  drag.active = false;
  drag.ghost.remove();
  drag.source.removeAttribute('data-amap-dragging');
  document.querySelectorAll('[data-amap-drop-hover="true"]').forEach((z) => z.removeAttribute('data-amap-drop-hover'));

  const zone = dropZoneAt(x, y);
  const durationMs = Date.now() - drag.startedAt;
  let detail = 'Drag released outside any drop zone.';
  if (zone && dispatchDrop) {
    zone.dispatchEvent(
      new CustomEvent('amapdrop', {
        detail: {
          source: 'gesture',
          zoneId: zone.getAttribute('data-amap-zone-id') || '',
          x,
          y,
          durationMs,
          pathPx: Math.round(drag.pathPx),
        },
        bubbles: true,
      })
    );
    detail = `Dropped onto ${zone.getAttribute('data-amap-zone-id') || 'drop zone'}.`;
  }
  activeDrag = null;
  return {
    ok: true,
    action: 'drag_end',
    target: describeElement(zone || drag.source),
    detail,
  };
}

/** End the active drag at viewport coordinates (dispatches a real drop). */
export function dragEnd(x: number, y: number): ExecutedActionResult {
  return endActiveDrag(x, y, true);
}

/** Cancel any active drag without dispatching a drop. */
export function dragCancel(): void {
  if (activeDrag) endActiveDrag(activeDrag.lastX, activeDrag.lastY, false);
}
