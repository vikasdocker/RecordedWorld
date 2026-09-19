#include "HUDWidget.h"

void UHUDWidget::UpdatePlayerCount(int32 Count)
{
	// TODO Phase F: Update player count text
	UE_LOG(LogTemp, Verbose, TEXT("Player count: %d"), Count);
}

void UHUDWidget::AddChatMessage(const FString& Username, const FString& Message)
{
	// TODO Phase F: Add message to chat scrollbox
	UE_LOG(LogTemp, Verbose, TEXT("Chat: %s: %s"), *Username, *Message);
}

void UHUDWidget::UpdateConnectionStatus(bool bConnected)
{
	// TODO Phase F: Update connection indicator
	UE_LOG(LogTemp, Verbose, TEXT("Connection: %s"), bConnected ? TEXT("Connected") : TEXT("Disconnected"));
}

void UHUDWidget::UpdateFPS(float Fps)
{
	// TODO Phase F: Update FPS counter
	UE_LOG(LogTemp, Verbose, TEXT("FPS: %.1f"), Fps);
}
