#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Components/TextRenderComponent.h"
#include "PlayerNameBillboard.generated.h"

UCLASS(ClassGroup=(Rendering), meta=(BlueprintSpawnableComponent))
class RECORDEDWORLD_API UPlayerNameBillboard : public UActorComponent
{
	GENERATED_BODY()

public:
	UPlayerNameBillboard();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category = "PlayerName")
	void SetPlayerName(const FString& NewName);

	UFUNCTION(BlueprintCallable, Category = "PlayerName")
	void SetNameColor(const FLinearColor& Color);

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "PlayerName")
	TObjectPtr<UTextRenderComponent> NameText;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "PlayerName")
	float HeightOffset = 120.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "PlayerName")
	float TextSize = 100.0f;

private:
	void UpdateBillboard();
};
