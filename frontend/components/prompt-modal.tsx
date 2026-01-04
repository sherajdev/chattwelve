"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PromptCard } from "./prompt-card"
import { PromptEditor } from "./prompt-editor"
import type { SystemPrompt } from "@/lib/types"

interface PromptModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  prompts: SystemPrompt[]
  onActivatePrompt: (id: string) => void
  onDeactivatePrompt: () => void
  onDeletePrompt: (id: string) => void
  onCreatePrompt: (name: string, content: string) => void
  onUpdatePrompt: (id: string, name: string, content: string) => void
}

export function PromptModal({
  open,
  onOpenChange,
  prompts,
  onActivatePrompt,
  onDeactivatePrompt,
  onDeletePrompt,
  onCreatePrompt,
  onUpdatePrompt,
}: PromptModalProps) {
  const activePrompt = prompts.find((p) => p.isActive)
  const myPrompts = prompts.filter((p) => !p.isActive)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>System Prompt Settings</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="active" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="my-prompts">My Prompts</TabsTrigger>
            <TabsTrigger value="create">Create New</TabsTrigger>
          </TabsList>

          {/* Active Prompt Tab */}
          <TabsContent value="active" className="space-y-4 mt-4 max-h-[60vh] overflow-y-auto">
            {activePrompt ? (
              <PromptCard
                prompt={activePrompt}
                onActivate={onActivatePrompt}
                onDeactivate={onDeactivatePrompt}
                onDelete={onDeletePrompt}
                onUpdate={onUpdatePrompt}
                isActive={true}
              />
            ) : (
              <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border">
                <p className="text-sm text-muted-foreground">No active prompt. Select one from "My Prompts".</p>
              </div>
            )}
          </TabsContent>

          {/* My Prompts Tab */}
          <TabsContent value="my-prompts" className="space-y-4 mt-4">
            <div className="space-y-3 max-h-[50vh] overflow-y-auto">
              {myPrompts.length > 0 ? (
                myPrompts.map((prompt) => (
                  <PromptCard
                    key={prompt.id}
                    prompt={prompt}
                    onActivate={onActivatePrompt}
                    onDeactivate={onDeactivatePrompt}
                    onDelete={onDeletePrompt}
                    onUpdate={onUpdatePrompt}
                    isActive={false}
                  />
                ))
              ) : (
                <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-border">
                  <p className="text-sm text-muted-foreground">No saved prompts. Create one in "Create New".</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Create New Tab */}
          <TabsContent value="create" className="mt-4 max-h-[60vh] overflow-y-auto">
            <PromptEditor onSave={onCreatePrompt} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
