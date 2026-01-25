# AppShell Layout Refactor – Fixed Viewport

## Overview
Refactored the AppShell component to use a **fixed viewport layout** with proper overflow handling. This ensures the interface maintains a consistent, scrollable structure without double-scrolling issues.

## Viewport Setup

### Global Styles (`ui/src/index.css`)
```css
html, body, #root {
  height: 100%;
  overflow: hidden;
}
```

- All three containers fixed to 100% viewport height
- Overflow hidden to prevent system scrollbars
- Scrolling handled at component level only

## Layout Structure

### AppShell (`ui/src/layouts/AppShell.tsx`)

```
┌─────────────────────────────────────────┐
│         Header (fixed height)           │  shrink-0
├────────┬──────────────────┬─────────────┤
│        │                  │             │  flex-1, overflow-hidden
│ Sidebar│   ChatView       │   Admin     │
│        │  (scrollable)    │   Panel     │
│  fixed │                  │   (fixed)   │
│ width  │  Composer        │             │
│        │  (fixed at bot)  │             │
├────────┴──────────────────┴─────────────┤
│        Footer (fixed height)            │  shrink-0
└─────────────────────────────────────────┘
```

**Key Structure:**
- **Root div**: `h-full w-full flex flex-col overflow-hidden`
  - Uses full viewport height/width
  - Flex column layout
  - No overflow

- **Header**: `shrink-0`
  - Fixed height (h-14, 56px)
  - Does not shrink

- **Main** (center area): `flex-1 min-h-0 flex overflow-hidden`
  - Grows to fill remaining space
  - `min-h-0` prevents flex overflow
  - `flex` for horizontal layout
  - No overflow (child controls)

- **Footer**: `shrink-0`
  - Fixed height (h-auto typically)
  - Does not shrink

## 3-Column Layout

### Left Sidebar
- **Width**: `w-72` (288px) with `min-w-[18rem]`
- **Responsive**: Hidden on mobile, visible on md+
- **Mobile**: Fixed overlay when `sidebarOpen=true`
- **Overflow**: `overflow-hidden` (managed by Sidebar component)
- **Styles**: `bg-neutral-900 border-r border-neutral-800`

### Center Column (Chat)
- **Growth**: `flex-1 min-w-0`
  - Fills available space
  - `min-w-0` allows flex to shrink below content width
- **Overflow**: `overflow-hidden` (scrolling in ChatView)
- **Internal Structure**:
  - Mobile menu trigger: `h-14 shrink-0` (visible on mobile only)
  - ChatView container: `flex-1 min-h-0 overflow-y-auto`
    - Scrollable vertical
    - `min-h-0` prevents flex overflow
  - Composer: `shrink-0` (fixed at bottom, no scroll)

### Right Admin Panel
- **Width**: `w-64` (256px) - fixed
- **Conditional**: Only renders if `profile?.is_admin`
- **Overflow**: Internal scroll only
- **Styles**: `flex flex-col shrink-0 border-l border-neutral-800 bg-neutral-900/60`
- **Header**: `shrink-0` (fixed section title)
- **Content**: `flex-1 min-h-0 overflow-y-auto` (scrollable)

## ChatPage Component

**Simplified structure:**
```tsx
<div className="flex h-full w-full flex-col overflow-hidden">
  {/* ChatView - scrollable */}
  <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto">
    <ChatView scrollRef={scrollRef} />
  </div>

  {/* Composer - fixed at bottom */}
  <div className="shrink-0">
    <Composer />
  </div>
</div>
```

- `h-full w-full`: Uses full viewport size from AppShell
- First div: `flex-1 min-h-0 overflow-y-auto` – scrolls vertically
- Second div: `shrink-0` – fixed height, no scroll

## Overflow Rules (Critical)

### ✅ Allowed to Scroll
- ChatView container (`.flex-1.overflow-y-auto`)
- Sidebar content (managed internally)
- Admin panel content (`.flex-1.min-h-0.overflow-y-auto`)

### ❌ Must NOT Scroll
- Root, AppShell, Header, Footer
- Main content area (overflow-hidden)
- Composer
- Mobile menu trigger bar

## Mobile Responsiveness

**Sidebar Behavior:**
- Hidden on mobile (via `hidden md:flex`)
- Shows as fixed overlay when `sidebarOpen=true`
- Position: `fixed inset-y-0 left-0 z-40`
- Overlay closes sidebar when clicked

**Mobile Menu Trigger:**
- Visible on mobile only (`md:hidden`)
- Height: `h-14` (matches header)
- Position: Fixed at top of center column
- Button to toggle sidebar

**Admin Panel:**
- Hidden on mobile (no conditional needed)
- AppShell only renders if `showAdminPanel=true`
- Always visible when admin user logs in

## Typography & Spacing

- **Header height**: 56px (h-14)
- **Mobile menu height**: 56px (h-14)
- **Sidebar width**: 288px (w-72)
- **Admin panel width**: 256px (w-64)
- **Chat max-width**: 4xl (56rem)
- **Padding**: 6 units (24px) on sides and vertical

## Flexbox Critical Patterns

```tsx
/* Flex column with scrollable child */
<div className="flex flex-col overflow-hidden">
  <div className="flex-1 min-h-0 overflow-y-auto">
    {/* scrollable content */}
  </div>
  <div className="shrink-0">
    {/* fixed footer */}
  </div>
</div>

/* Flex row with fixed sidebar */
<div className="flex overflow-hidden">
  <aside className="w-72 shrink-0 overflow-hidden">
    {/* fixed width sidebar */}
  </aside>
  <div className="flex-1 min-w-0">
    {/* flexible main area */}
  </div>
</div>
```

## Browser Compatibility

- ✅ Modern browsers (Chrome, Firefox, Safari, Edge)
- ✅ Mobile browsers
- ✅ Responsive (md breakpoint at 768px)
- ✅ CSS Grid and Flexbox support required

## Testing Checklist

- [ ] Desktop: All columns visible (sidebar + chat + admin)
- [ ] Tablet: Sidebar toggle works
- [ ] Mobile: Menu works, single column layout
- [ ] Chat scrolls independently
- [ ] Composer stays at bottom while scrolling
- [ ] Admin panel scrolls internally
- [ ] Header/Footer don't scroll
- [ ] No double-scroll issues
- [ ] Window resize doesn't break layout
