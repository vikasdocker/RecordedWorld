#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "RWPlayerController.generated.h"

class UInputMappingContext;
class UInputAction;
struct FInputActionValue;

UCLASS()
class RECORDEDWORLD_API ARWPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ARWPlayerController();

	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void Tick(float DeltaTime) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Player")
	FString Username = TEXT("Player");

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player")
	bool bIsConnected = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Player")
	bool bIsMoving = false;

	UFUNCTION(BlueprintCallable, Category = "Player")
	void SetUsername(const FString& NewUsername);

	void MoveForward(const FInputActionValue& Value);
	void MoveRight(const FInputActionValue& Value);
	void LookUp(const FInputActionValue& Value);
	void TurnRight(const FInputActionValue& Value);

protected:
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputMappingContext> DefaultMappingContext;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MoveForwardAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> MoveRightAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> LookUpAction;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Input")
	TObjectPtr<UInputAction> TurnRightAction;
};
