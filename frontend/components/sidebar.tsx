"use client"

import { Plus, Trash2, Menu } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import type { ChatSession } from "@/lib/types"
import { useState } from "react"
import Image from "next/image"

interface SidebarProps {
  sessions: ChatSession[]
  activeSessionId: string | null
  onNewChat: () => void
  onSelectSession: (id: string) => void
  onDeleteSession: (id: string) => void
}

function SidebarContent({ sessions, activeSessionId, onNewChat, onSelectSession, onDeleteSession }: SidebarProps) {
  return (
    <div className="flex h-full w-60 flex-col bg-sidebar">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-sidebar-border p-4">
        <Image
          src="/logo.png"
          alt="ChatTwelve Logo"
          width={32}
          height={32}
          className="rounded-lg"
        />
        <h1 className="text-lg font-semibold text-sidebar-foreground">ChatTwelve</h1>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <Button
          onClick={onNewChat}
          className="w-full justify-start gap-2 bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Chat Sessions List */}
      <ScrollArea className="flex-1 px-3">
        <div className="space-y-1 pb-4">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
                activeSessionId === session.id
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              <button onClick={() => onSelectSession(session.id)} className="flex-1 truncate text-left">
                {session.title}
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDeleteSession(session.id)
                }}
                className="opacity-0 transition-opacity group-hover:opacity-100"
              >
                <Trash2 className="h-3.5 w-3.5 text-sidebar-foreground/60 hover:text-destructive" />
              </button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

export function Sidebar(props: SidebarProps) {
  return (
    <>
      {/* Desktop Sidebar */}
      <div className="hidden md:block">
        <SidebarContent {...props} />
      </div>

      {/* Mobile Sidebar (Drawer) */}
      <div className="md:hidden">
        <MobileSidebar {...props} />
      </div>
    </>
  )
}

function MobileSidebar(props: SidebarProps) {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="fixed left-4 top-4 z-40 md:hidden">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-60 p-0">
        <SidebarContent {...props} />
      </SheetContent>
    </Sheet>
  )
}
