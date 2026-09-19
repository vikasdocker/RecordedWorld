#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HUDWidget.generated.h"

UCLASS()
class RECORDEDWORLD_API UHUDWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "HUD")
	void UpdatePlayerCount(int32 Count);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void AddChatMessage(const FString& Username, const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void UpdateConnectionStatus(bool bConnected);

	UFUNCTION(BlueprintCallable, Category = "HUD")
	void UpdateFPS(float Fps);

protected:
	UPROPERTY(meta = (BindWidget))
	TObjectPtr<class UTextBlock> PlayerCountText;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<class UTextBlock> ConnectionStatusText;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<class UTextBlock> FPSText;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<class UScrollBox> ChatScrollBox;

	UPROPERTY(meta = (BindWidget))
	TObjectPtr<class UEditableTextBox> ChatInputBox;
};
